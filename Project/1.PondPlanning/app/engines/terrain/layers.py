"""Layer descriptors: how the map client reaches each raster the pipeline wrote."""

from __future__ import annotations

from urllib.parse import quote
from uuid import UUID

from app.domain.units import Quantity, Unit
from app.engines.village import ESRI_WORLD_IMAGERY
from app.providers.storage import ObjectStore
from app.repositories.records import DEMAssetRecord
from app.schemas.common import QuantityOut, ResultWarning
from app.schemas.terrain import DEMAsset, LayerDescriptor, TerrainLayers


def _titiler_template(tiles_base: str, source_url: str, query: str) -> str:
    return (
        f"{tiles_base}/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}.png"
        f"?url={quote(source_url, safe='')}&{query}"
    )


def layer_descriptors(
    asset: DEMAssetRecord, store: ObjectStore, tiles_base: str
) -> list[LayerDescriptor]:
    """Satellite basemap plus every raster derived so far for this village."""
    stats = asset.statistics
    layers = [
        LayerDescriptor(
            layer_id="satellite",
            kind="raster",
            title="Satellite imagery",
            tile_url_template=ESRI_WORLD_IMAGERY.tile_url_template,
            source=ESRI_WORLD_IMAGERY.provider,
        )
    ]
    if asset.hillshade_key:
        layers.append(
            LayerDescriptor(
                layer_id="hillshade",
                kind="raster",
                title="Hillshade",
                tile_url_template=_titiler_template(
                    tiles_base,
                    store.url(asset.hillshade_key),
                    f"rescale={stats.get('hillshade_p2', 1):g},{stats.get('hillshade_p98', 255):g}",
                ),
                source=f"{asset.source} · Horn (1981), azimuth 315°, altitude 45°",
            )
        )
    lo, hi = float(stats["min"]), float(stats["max"])
    layers.append(
        LayerDescriptor(
            layer_id="dem",
            kind="raster",
            title="Elevation",
            tile_url_template=_titiler_template(
                tiles_base, store.url(asset.dem_key), f"rescale={lo:g},{hi:g}&colormap_name=terrain"
            ),
            units="m",
            value_range=[lo, hi],
            source=f"{asset.source} · {asset.method}",
        )
    )
    return layers


def terrain_layers(
    village_id: UUID, asset: DEMAssetRecord, store: ObjectStore, tiles_base: str
) -> TerrainLayers:
    """The FR8 layer list for a village."""
    return TerrainLayers(village_id=village_id, layers=layer_descriptors(asset, store, tiles_base))


def dem_asset_out(
    asset: DEMAssetRecord, extra_warnings: list[ResultWarning] | None = None
) -> DEMAsset:
    """Wire form of the DEM provenance row."""

    def metres(value: float, method: str | None = None) -> QuantityOut:
        return QuantityOut.from_domain(Quantity(value, Unit.METRE, None, method))

    warnings = list(extra_warnings or [])
    return DEMAsset(
        village_id=asset.village_id,
        source=asset.source,
        native_resolution=metres(asset.native_resolution_m),
        working_resolution=metres(
            asset.working_resolution_m,
            "derived from mean contour spacing, floored at the source resolution",
        ),
        vertical_accuracy_relative=metres(asset.vertical_accuracy_relative_m, "relative, LE90"),
        vertical_accuracy_absolute=metres(asset.vertical_accuracy_absolute_m, "absolute, LE90"),
        crs=f"EPSG:{asset.epsg}",
        acquired=asset.acquired,
        attribution=list(asset.attribution),
        warnings=warnings,
    )
