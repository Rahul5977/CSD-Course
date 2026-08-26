"""The ``POST /analysis/runoff`` pipeline (FR6).

catchment polygon → land cover window (WorldCover) → soil group (SoilGrids)
→ composite curve number → daily rainfall at the outlet → three methods on
the daily series → annual runoff depths → 75 % dependable and mean volumes,
reported as a range with the spread.

Every external lookup degrades to a stated default with a warning rather
than failing the job: a runoff figure with a caveat beats no figure.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

import numpy as np

from app.domain.errors import DomainError, NotFoundError, UpstreamUnavailableError
from app.domain.rainfall import DailyRainfall
from app.domain.units import Quantity, Unit
from app.engines.rainfall.service import fetch_record
from app.engines.rainfall.statistics import weibull_dependable
from app.engines.runoff.curve_number import (
    WORLDCOVER_NAMES,
    CurveNumber,
    composite_curve_number,
)
from app.engines.runoff.methods import (
    AnnualRunoff,
    RationalMethod,
    RunoffMethod,
    SCSCNMethod,
    StrangeMethod,
)
from app.providers.landcover import (
    ConstantLandCoverAdapter,
    DefaultSoilAdapter,
    LandCoverWindow,
    SoilGridsAdapter,
    SoilTexture,
    WorldCoverAdapter,
)
from app.providers.raster_io import rasterize_polygon
from app.providers.resilience import FallbackChain
from app.providers.storage import ObjectStore
from app.repositories import Repositories
from app.schemas.analysis import CatchmentResult, RunoffMethodResult, RunoffResult
from app.schemas.common import QuantityOut, ResultWarning

logger = logging.getLogger(__name__)

#: Documented uncertainty per method (annual volume). CN literature: ±25-35 %.
METHOD_UNCERTAINTY_PCT = {"scs_cn": 30.0, "rational": 40.0, "empirical_strange": 35.0}
SOIL_CACHE_TTL_S = 30 * 86_400


def _soil(store: ObjectStore, lon: float, lat: float, warnings: list[ResultWarning]) -> SoilTexture:
    key = f"soil/{lat:.3f}_{lon:.3f}.json"
    if store.exists(key):
        doc = json.loads(store.get(key))
        if time.time() - float(doc["stored_at"]) < SOIL_CACHE_TTL_S:
            return SoilTexture(doc["clay"], doc["sand"], doc["hsg"], doc["source"], doc["assumed"])
    try:
        texture = SoilGridsAdapter().texture(lon, lat)
    except UpstreamUnavailableError as exc:
        logger.warning("soil lookup failed", extra={"reason": exc.message})
        texture = DefaultSoilAdapter().texture(lon, lat)
        warnings.append(
            ResultWarning(
                code="soil_assumed",
                message="SoilGrids was unreachable; hydrologic soil group C (central-Indian "
                "loams) was assumed. Curve number uncertainty is wider.",
                severity="caution",
            )
        )
    store.put(
        key,
        json.dumps(
            {
                "clay": texture.clay_pct,
                "sand": texture.sand_pct,
                "hsg": texture.hsg,
                "source": texture.source,
                "assumed": texture.assumed,
                "stored_at": time.time(),
            }
        ).encode(),
        "application/json",
    )
    return texture


def _landcover(
    bounds: tuple[float, float, float, float], warnings: list[ResultWarning]
) -> LandCoverWindow:
    try:
        return WorldCoverAdapter().window(bounds)
    except UpstreamUnavailableError as exc:
        logger.warning("land cover lookup failed", extra={"reason": exc.message})
        warnings.append(
            ResultWarning(
                code="landcover_assumed",
                message="ESA WorldCover was unreachable; cropland was assumed over the whole "
                "catchment.",
                severity="caution",
            )
        )
        return ConstantLandCoverAdapter().window(bounds)


def curve_number_for(
    catchment: CatchmentResult, store: ObjectStore, warnings: list[ResultWarning]
) -> CurveNumber:
    """Composite CN over the catchment polygon from live (or assumed) land cover and soil."""
    geometry = catchment.geojson.features[0].geometry
    lon, lat = catchment.snapped_point.lon, catchment.snapped_point.lat
    coords = np.array(
        [
            pt
            for ring in (
                geometry["coordinates"]
                if geometry["type"] == "Polygon"
                else [r for poly in geometry["coordinates"] for r in poly]
            )
            for pt in ring
        ],
        dtype=float,
    )
    bounds = (
        float(coords[:, 0].min()) - 0.001,
        float(coords[:, 1].min()) - 0.001,
        float(coords[:, 0].max()) + 0.001,
        float(coords[:, 1].max()) + 0.001,
    )
    window = _landcover(bounds, warnings)
    inside = rasterize_polygon(geometry, window.codes.shape, window.transform)
    codes = np.where(inside, window.codes, 0)
    texture = _soil(store, lon, lat, warnings)
    cn = composite_curve_number(codes, texture.hsg, "II", f"{window.source}; {texture.source}")
    if window.assumed or texture.assumed:
        cn = CurveNumber(
            cn.cn, cn.hsg, cn.amc, cn.class_fractions, cn.class_cn, cn.runoff_coefficient, cn.source
        )
    return cn


def _method_result(
    method: RunoffMethod, annual: AnnualRunoff, area_m2: float, key: str
) -> RunoffMethodResult:
    q = QuantityOut.from_domain
    unc = METHOD_UNCERTAINTY_PCT[key]
    dependable_mm = weibull_dependable(annual.runoff_mm, 0.75)
    params = {
        name: q(Quantity(value, Unit(unit), None, note))
        for name, (value, unit, note) in method.parameters().items()
    }
    params["mean_annual_runoff_depth"] = q(
        Quantity(float(annual.runoff_mm.mean()), Unit.MILLIMETRE, unc, "mean of annual sums")
    )
    params["dependable_75_runoff_depth"] = q(
        Quantity(dependable_mm, Unit.MILLIMETRE, unc, "Weibull 75 % on annual runoff")
    )
    params["years"] = q(Quantity(float(len(annual.years)), Unit.COUNT, None, "complete years"))
    return RunoffMethodResult(
        method=key,  # type: ignore[arg-type]
        annual_runoff_volume=q(
            Quantity(
                dependable_mm / 1000.0 * area_m2,
                Unit.CUBIC_METRE,
                unc,
                f"{key}: 75 % dependable annual runoff depth x catchment area",
            )
        ),
        runoff_coefficient=q(
            Quantity(annual.mean_coefficient, Unit.RATIO, unc, "mean annual runoff / rainfall")
        ),
        parameters=params,
        reference=method.reference,
    )


def compute_runoff(
    catchment: CatchmentResult,
    record: DailyRainfall,
    cn: CurveNumber,
    methods: list[str],
    village_id: UUID,
    warnings: list[ResultWarning],
) -> RunoffResult:
    """Run the requested methods and assemble the range."""
    area_m2 = catchment.area.value * 1e4
    strategies: dict[str, RunoffMethod] = {
        "scs_cn": SCSCNMethod(cn),
        "rational": RationalMethod(cn.runoff_coefficient),
        "empirical_strange": StrangeMethod("average"),
    }
    results = [
        _method_result(strategies[k], strategies[k].annual(record), area_m2, k)
        for k in methods
        if k in strategies
    ]
    if not results:
        msg = "no known runoff method requested"
        raise NotFoundError(msg, {"requested": methods, "known": list(strategies)})
    volumes = np.array([r.annual_runoff_volume.value for r in results])
    spread = float(100.0 * (volumes.max() - volumes.min()) / max(volumes.mean(), 1e-9))
    recommended = next((r for r in results if r.method == "scs_cn"), results[0])
    q = QuantityOut.from_domain
    if spread > 60:
        warnings.append(
            ResultWarning(
                code="methods_disagree",
                message=f"The methods disagree by {spread:.0f} %; treat the SCS-CN figure as "
                "planning-grade and confirm with a season of observation.",
                severity="caution",
            )
        )
    class_note = ", ".join(
        f"{WORLDCOVER_NAMES.get(code, code)} {share:.0%}"
        for code, share in sorted(cn.class_fractions.items(), key=lambda kv: -kv[1])[:4]
    )
    warnings.append(
        ResultWarning(
            code="curve_number_basis",
            message=f"CN {cn.cn:.0f} (HSG {cn.hsg}, AMC {cn.amc}) from "
            f"{class_note or 'assumed cropland'}; {cn.source}.",
            severity="info",
        )
    )
    return RunoffResult(
        village_id=village_id,
        catchment_area=catchment.area,
        results=results,
        recommended=recommended,
        spread_pct=q(Quantity(spread, Unit.PERCENT, None, "(max - min) / mean across methods")),
        warnings=warnings,
    )


def run_runoff(
    job_id: UUID, repos: Repositories, store: ObjectStore, rainfall: FallbackChain
) -> dict[str, Any]:
    """Execute a queued runoff job."""
    jobs = repos.jobs
    job = jobs.get(job_id)
    if job is None:
        msg = "job not found"
        raise NotFoundError(msg, {"job_id": str(job_id)})
    try:
        params = job.params
        village_id = UUID(str(params["village_id"]))
        jobs.update(job_id, status="running", progress=10, stage="loading catchment")
        catchment_job = jobs.get(UUID(str(params["catchment_job_id"])))
        if catchment_job is None or catchment_job.status != "succeeded" or not catchment_job.result:
            msg = "catchment job not found or not finished"
            raise NotFoundError(msg, {"catchment_job_id": params["catchment_job_id"]})
        result = catchment_job.result
        catchment = CatchmentResult.model_validate(result.get("catchment", result))
        warnings: list[ResultWarning] = []
        jobs.update(job_id, status="running", progress=30, stage="land cover and soil")
        if params.get("curve_number"):
            cn = CurveNumber(
                float(params["curve_number"]), "C", "II", {}, {}, 0.35, "user override"
            )
        else:
            cn = curve_number_for(catchment, store, warnings)
        jobs.update(job_id, status="running", progress=60, stage="daily rainfall")
        record = fetch_record(
            rainfall,
            catchment.snapped_point.lon,
            catchment.snapped_point.lat,
            int(params.get("years") or 20),
        )
        if not record.fetched_live:
            warnings.append(
                ResultWarning(
                    code="stale_data", message="rainfall served from cache", severity="caution"
                )
            )
        jobs.update(job_id, status="running", progress=80, stage="runoff by three methods")
        methods: list[str] = list(
            params.get("methods") or ["scs_cn", "rational", "empirical_strange"]
        )
        out = compute_runoff(catchment, record, cn, methods, village_id, warnings).model_dump(
            mode="json"
        )
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


Condition = Literal["good", "average", "bad"]
