"""The ``POST /analysis/pond-design`` pipeline (FR7) — the project's headline result.

catchment (snap + delineate) → daily rainfall → curve number → runoff (three
methods) → the natural elevation-area-volume curve at the site → target
storage → cost-optimised excavated geometry → losses and dead storage →
daily water balance over the record (fill reliability) → 25-year spillway
→ bill of quantities → confidence label. Assembled by :class:`PondDesignBuilder`
so each stage is a named method that can be tested and explained alone.

Every number carries its unit and band; the confidence label is decided
from the worst of the inputs (DEM source, assumed land cover / soil, cached
rainfall), so a 30 m-DEM result cannot read as a survey.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

import numpy as np
from pyproj import Transformer

from app.domain.errors import DomainError, NotFoundError
from app.domain.rainfall import DailyRainfall
from app.domain.units import Quantity, Unit
from app.engines.design.eav import eav_curve
from app.engines.design.geometry import PondGeometry
from app.engines.design.optimiser import CostRates, DesignChoice, optimise
from app.engines.design.spillway import size_spillway
from app.engines.design.water_balance import BalanceResult, simulate
from app.engines.hydrology.catchment import delineate
from app.engines.rainfall.service import fetch_record
from app.engines.rainfall.statistics import compute_statistics
from app.engines.runoff.curve_number import CurveNumber
from app.engines.runoff.methods import SCSCNMethod
from app.engines.workflows.catchment import FLOW_MODELS, catchment_result
from app.engines.workflows.runoff import compute_runoff, curve_number_for
from app.providers.resilience import FallbackChain
from app.providers.storage import ObjectStore
from app.repositories import Repositories
from app.schemas.analysis import (
    BillOfQuantities,
    CatchmentResult,
    EAVPoint,
    PondDesignResult,
    PondDimensions,
    PourPoint,
    RunoffResult,
)
from app.schemas.common import QuantityOut, ResultWarning

logger = logging.getLogger(__name__)

HARVEST_EFFICIENCY = 0.6  # of catchment runoff reaching the pond; 0.5-0.7 in practice
MAX_STORAGE_M3 = 50_000.0  # a village pond, not a reservoir; Amrit Sarovar minimum is 10 000
MIN_STORAGE_M3 = 2_000.0
DEAD_STORAGE_FRACTION = 0.15
STORAGE_UNCERTAINTY_PCT = 20.0

q = QuantityOut.from_domain


class PondDesignBuilder:
    """Builder: each stage adds a named part; :meth:`build` assembles the payload."""

    def __init__(self, village_id: UUID, warnings: list[ResultWarning]) -> None:
        """Start an empty design for a village."""
        self.village_id = village_id
        self.warnings = warnings
        self.catchment: CatchmentResult | None = None
        self.record: DailyRainfall | None = None
        self.cn: CurveNumber | None = None
        self.runoff: RunoffResult | None = None
        self.natural_eav: list[Any] = []
        self.target_m3 = 0.0
        self.harvestable_m3 = 0.0
        self.choice: DesignChoice | None = None
        self.balance: BalanceResult | None = None
        self.spillway_length_m = 0.0
        self.spillway_peak_m3_s = 0.0
        self.rates = CostRates()

    # -- stages -------------------------------------------------------------
    def with_catchment(self, catchment: CatchmentResult) -> PondDesignBuilder:
        """Stage 1: the contributing area."""
        self.catchment = catchment
        return self

    def with_rainfall(self, record: DailyRainfall) -> PondDesignBuilder:
        """Stage 2: the daily record at the site."""
        self.record = record
        return self

    def with_runoff(self, cn: CurveNumber, runoff: RunoffResult) -> PondDesignBuilder:
        """Stage 3: curve number and the three-method runoff range."""
        self.cn, self.runoff = cn, runoff
        return self

    def with_natural_eav(self, points: list[Any]) -> PondDesignBuilder:
        """Stage 4: what a bund alone would impound."""
        self.natural_eav = points
        return self

    def size(self, target_reliability: float, max_depth_m: float | None) -> PondDesignBuilder:
        """Stage 5: target storage → cheapest geometry → water balance → spillway."""
        assert self.catchment and self.record and self.cn and self.runoff
        area_m2 = self.catchment.area.value * 1e4
        dependable_depth_mm = self.runoff.recommended.parameters["dependable_75_runoff_depth"].value
        self.harvestable_m3 = dependable_depth_mm / 1000.0 * area_m2 * HARVEST_EFFICIENCY
        self.target_m3 = float(np.clip(self.harvestable_m3, MIN_STORAGE_M3, MAX_STORAGE_M3))
        if self.harvestable_m3 > MAX_STORAGE_M3:
            self.warnings.append(
                ResultWarning(
                    code="storage_capped",
                    message=f"The catchment can harvest ~{self.harvestable_m3:,.0f} m³ in a 75 % "
                    f"dependable year; the pond is sized at {MAX_STORAGE_M3:,.0f} m³ (a village "
                    "pond, not a reservoir) and the surplus spills.",
                    severity="info",
                )
            )
        best, _ = optimise(self.target_m3, max_depth_m=max_depth_m, rates=self.rates)
        self.choice = best
        daily = SCSCNMethod(self.cn)
        s = self.cn.potential_retention_mm
        ia = daily.ia_ratio * s
        p = np.nan_to_num(self.record.mm, nan=0.0)
        excess = np.maximum(p - ia, 0.0)
        daily_runoff = np.where(p > ia, excess**2 / (excess + s), 0.0)
        self.balance = simulate(
            self.record,
            daily_runoff,
            area_m2,
            best.geometry,
            harvest_efficiency=HARVEST_EFFICIENCY,
            dead_storage_fraction=DEAD_STORAGE_FRACTION,
        )
        if self.balance.fill_reliability < target_reliability:
            self.warnings.append(
                ResultWarning(
                    code="reliability_below_target",
                    message=f"The pond fills in {self.balance.fill_reliability:.0%} of years, "
                    f"below the {target_reliability:.0%} target; consider a smaller pond or a "
                    "larger intake.",
                    severity="caution",
                )
            )
        stats = compute_statistics(self.record)
        spill = size_spillway(
            rainfall_25y_1day_mm=stats.return_period_25y_1day_mm,
            longest_flow_path_m=self.catchment.longest_flow_path.value,
            mean_slope_ratio=float(np.tan(np.radians(self.catchment.mean_slope.value))),
            catchment_area_m2=area_m2,
            runoff_coefficient=self.cn.runoff_coefficient,
        )
        self.spillway_length_m, self.spillway_peak_m3_s = spill.weir_length_m, spill.peak_flow_m3_s
        self.rainfall_stats = stats
        return self

    # -- assembly -----------------------------------------------------------
    def confidence(self) -> tuple[Literal["low", "moderate", "high"], str]:
        """Worst-input rule."""
        codes = {w.code for w in self.warnings}
        reasons: list[str] = []
        level: Literal["low", "moderate", "high"] = "moderate"
        if "landcover_assumed" in codes or "soil_assumed" in codes:
            level = "low"
            reasons.append("land cover or soil group assumed")
        if "stale_data" in codes:
            reasons.append("rainfall from cache")
        if (
            self.catchment
            and self.catchment.area.uncertainty_pct
            and self.catchment.area.uncertainty_pct > 25
        ):
            level = "low"
            reasons.append("coarse catchment (edge-limited or few cells)")
        reasons.append(
            "DEM is contour-interpolated from a ~30 m source: planning grade, not survey grade"
        )
        return level, "; ".join(reasons)

    def build(self) -> PondDesignResult:
        """Assemble the payload."""
        assert self.catchment and self.runoff and self.choice and self.balance and self.record
        g = self.choice.geometry
        gross = g.storage_m3
        dead = DEAD_STORAGE_FRACTION * gross
        eav = [
            EAVPoint(
                elevation=q(Quantity(level, Unit.METRE, None, "above pond floor")),
                surface_area=q(
                    Quantity(
                        g.area_at_level(level),
                        Unit.SQUARE_METRE,
                        STORAGE_UNCERTAINTY_PCT,
                        "frustum",
                    )
                ),
                cumulative_volume=q(
                    Quantity(
                        g.volume_at_level(level),
                        Unit.CUBIC_METRE,
                        STORAGE_UNCERTAINTY_PCT,
                        "prismoidal",
                    )
                ),
            )
            for level in np.arange(0.0, g.depth_m + 1e-9, 0.25)
        ]
        stats = self.rainfall_stats
        level, rationale = self.confidence()
        cost = self.choice.cost_inr
        return PondDesignResult(
            village_id=self.village_id,
            catchment=self.catchment,
            rainfall_summary={
                "mean_annual": q(
                    Quantity(
                        stats.mean_annual_mm,
                        Unit.MILLIMETRE_PER_YEAR,
                        15.0,
                        "mean of complete years",
                    )
                ),
                "dependable_75": q(
                    Quantity(
                        stats.dependable_75_mm, Unit.MILLIMETRE_PER_YEAR, 15.0, "Weibull m/(n+1)"
                    )
                ),
                "monsoon_share": q(Quantity(stats.monsoon_share_pct, Unit.PERCENT, 3.0, "Jun-Sep")),
                "rainfall_25y_1day": q(
                    Quantity(
                        stats.return_period_25y_1day_mm,
                        Unit.MILLIMETRE,
                        25.0,
                        "Gumbel EV1, method of moments",
                    )
                ),
                "years_of_record": q(Quantity(float(stats.years), Unit.COUNT, None, None)),
            },
            runoff=self.runoff,
            dimensions=PondDimensions(
                depth=q(Quantity(g.depth_m, Unit.METRE, None, "cost-optimised over 1.5-3.5 m")),
                top_length=q(
                    Quantity(g.top_length_m, Unit.METRE, 5.0, "frustum solved for target storage")
                ),
                top_width=q(
                    Quantity(g.top_width_m, Unit.METRE, 5.0, "frustum solved for target storage")
                ),
                bottom_length=q(
                    Quantity(g.bottom_length_m, Unit.METRE, 5.0, "top inset by side slopes")
                ),
                bottom_width=q(
                    Quantity(g.bottom_width_m, Unit.METRE, 5.0, "top inset by side slopes")
                ),
                side_slope=q(Quantity(g.side_slope, Unit.RATIO, None, "H:V, earthen")),
                freeboard=q(Quantity(g.freeboard_m, Unit.METRE, None, "above design water level")),
            ),
            gross_storage=q(
                Quantity(
                    gross, Unit.CUBIC_METRE, STORAGE_UNCERTAINTY_PCT, "prismoidal frustum volume"
                )
            ),
            live_storage=q(
                Quantity(
                    gross - dead,
                    Unit.CUBIC_METRE,
                    STORAGE_UNCERTAINTY_PCT,
                    "gross minus dead storage",
                )
            ),
            dead_storage=q(
                Quantity(
                    dead,
                    Unit.CUBIC_METRE,
                    STORAGE_UNCERTAINTY_PCT,
                    f"{DEAD_STORAGE_FRACTION:.0%} silt allowance",
                )
            ),
            eav_curve=eav,
            reliability=q(
                Quantity(
                    self.balance.fill_reliability,
                    Unit.RATIO,
                    10.0,
                    f"daily water balance over {self.balance.years} years: "
                    "years reaching >= 90 % full",
                )
            ),
            bill_of_quantities=BillOfQuantities(
                excavation_volume=q(
                    Quantity(
                        self.choice.excavation_m3,
                        Unit.CUBIC_METRE,
                        15.0,
                        "frustum incl. freeboard band",
                    )
                ),
                embankment_volume=q(
                    Quantity(
                        self.choice.embankment_m3,
                        Unit.CUBIC_METRE,
                        25.0,
                        "1 m spoil bund, 2 m crest, 2:1 slopes",
                    )
                ),
                indicative_cost=q(
                    Quantity(cost, Unit.INR, 30.0, "excavation + embankment at indicative rates")
                ),
                cost_basis=self.rates.basis,
            ),
            confidence=level,
            confidence_rationale=rationale,
            warnings=[
                *self.warnings,
                ResultWarning(
                    code="water_balance",
                    message=(
                        f"Fills (>= 90 %) in {self.balance.fill_reliability:.0%} of years; "
                        f"water above dead storage {self.balance.months_with_water_mean:.1f} "
                        "months/yr on average; mean annual spill "
                        f"{self.balance.mean_annual_spill_m3:,.0f} m³, evaporation "
                        f"{self.balance.mean_annual_evaporation_m3:,.0f} m³, seepage "
                        f"{self.balance.mean_annual_seepage_m3:,.0f} m³ (2 mm/day). Spillway: "
                        f"{self.spillway_length_m:.1f} m weir for a 25-yr peak of "
                        f"{self.spillway_peak_m3_s:.2f} m³/s."
                    ),
                    severity="info",
                ),
                ResultWarning(
                    code="natural_impoundment",
                    message=(
                        "Without excavation, a bund at this point would impound "
                        + ", ".join(
                            f"{p.volume_m3:,.0f} m³ at +{p.level_m:g} m"
                            for p in self.natural_eav[4::4]
                        )
                        + " (from the DEM)."
                    ),
                    severity="info",
                ),
            ],
        )


def run_pond_design(
    job_id: UUID,
    repos: Repositories,
    store: ObjectStore,
    rainfall: FallbackChain,
    *,
    snap_radius_m: float,
    min_channel_area_m2: float,
) -> dict[str, Any]:
    """Execute a queued pond-design job."""
    jobs = repos.jobs
    job = jobs.get(job_id)
    if job is None:
        msg = "job not found"
        raise NotFoundError(msg, {"job_id": str(job_id)})
    try:
        params = job.params
        village_id = UUID(str(params["village_id"]))
        asset = repos.dem_assets.get_for_village(village_id)
        if asset is None:
            msg = "this village has no terrain yet — analyse a contour map first"
            raise NotFoundError(msg, {"village_id": str(village_id)})
        warnings: list[ResultWarning] = []
        builder = PondDesignBuilder(village_id, warnings)

        jobs.update(job_id, status="running", progress=10, stage="delineating catchment")
        model, slope = FLOW_MODELS.get(store, asset)
        point = PourPoint(**params["pour_point"])
        grid = model.filled.grid
        x, y = Transformer.from_crs("EPSG:4326", f"EPSG:{grid.epsg}", always_xy=True).transform(
            point.lon, point.lat
        )
        row, col = grid.index_of(x, y)
        catchment = delineate(
            model, row, col, radius_m=snap_radius_m, min_area_m2=min_channel_area_m2
        )
        catchment_out = catchment_result(
            village_id, model, slope, catchment, point, asset.vertical_accuracy_relative_m
        )
        builder.with_catchment(catchment_out)

        jobs.update(job_id, status="running", progress=30, stage="daily rainfall")
        record = fetch_record(
            rainfall, catchment_out.snapped_point.lon, catchment_out.snapped_point.lat, 25
        )
        if not record.fetched_live:
            warnings.append(
                ResultWarning(
                    code="stale_data", message="rainfall served from cache", severity="caution"
                )
            )
        builder.with_rainfall(record)

        jobs.update(job_id, status="running", progress=50, stage="curve number and runoff")
        cn = curve_number_for(catchment_out, store, warnings)
        runoff = compute_runoff(
            catchment_out,
            record,
            cn,
            ["scs_cn", "rational", "empirical_strange"],
            village_id,
            warnings,
        )
        builder.with_runoff(cn, runoff)

        jobs.update(job_id, status="running", progress=65, stage="elevation-area-volume")
        builder.with_natural_eav(eav_curve(model, catchment.outlet.row, catchment.outlet.col))

        jobs.update(job_id, status="running", progress=80, stage="sizing, water balance, spillway")
        builder.size(float(params.get("target_reliability") or 0.75), params.get("max_depth"))
        out = builder.build().model_dump(mode="json")
        jobs.update(
            job_id,
            status="succeeded",
            progress=100,
            stage="done",
            result=out,
            village_id=village_id,
            finished_at=datetime.now(UTC),
        )
        return out
    except DomainError as exc:
        jobs.update(
            job_id,
            status="failed",
            stage="failed",
            error=f"{exc.code}: {exc.message}",
            result={"code": exc.code, "message": exc.message, "detail": exc.detail},
            finished_at=datetime.now(UTC),
        )
        raise
    except ValueError as exc:  # optimiser: no feasible geometry
        jobs.update(
            job_id,
            status="failed",
            stage="failed",
            error=f"design_infeasible: {exc}",
            result={"code": "design_infeasible", "message": str(exc), "detail": {}},
            finished_at=datetime.now(UTC),
        )
        raise


__all__ = ["PondDesignBuilder", "PondGeometry", "run_pond_design"]
