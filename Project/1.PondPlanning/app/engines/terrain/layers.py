"""Layer descriptors: how the map client reaches each raster the pipeline wrote."""

from __future__ import annotations

from urllib.parse import quote
from uuid import UUID

from app.domain.units import Quantity, Unit
from app.engines.village import ESRI_WORLD_IMAGERY
from app.engines.workflows.terrain_products import PRODUCTS
from app.providers.storage import ObjectStore
from app.repositories.records import DEMAssetRecord
from app.schemas.common import QuantityOut, ResultWarning
from app.schemas.terrain import DEMAsset, LayerDescriptor, TerrainLayers


def _titiler_template(tiles_base: str, source_url: str, query: str) -> str:
    return (
        f"{tiles_base}/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}.png"
        f"?url={quote(source_url, safe='')}&{query}"
    )


def raster_layer(
    asset: DEMAssetRecord, product_id: str, store: ObjectStore, tiles_base: str
) -> LayerDescriptor:
    """Describe one stored raster product as a TiTiler layer."""
    product = PRODUCTS[product_id]
    stats = asset.statistics
    if product.fixed_range is not None:
        lo, hi = product.fixed_range
    else:
        lo = float(stats.get(f"{product_id}_p2", stats.get("min", 0.0)))
        hi = float(stats.get(f"{product_id}_p98", stats.get("max", 1.0)))
        if hi <= lo:
            hi = lo + 1.0
    query = f"rescale={lo:g},{hi:g}"
    if product.colormap:
        query += f"&colormap_name={product.colormap}"
    return LayerDescriptor(
        layer_id=product.layer_id,
        kind="raster",
        title=product.title,
        tile_url_template=_titiler_template(
            tiles_base, store.url(f"villages/{asset.village_id}/{product.key}"), query
        ),
        units=product.units,
        value_range=[lo, hi],
        source=f"{asset.source} · {product.algorithm}",
    )


def layer_descriptors(
    asset: DEMAssetRecord, store: ObjectStore, tiles_base: str
) -> list[LayerDescriptor]:
    """Satellite basemap, every stored raster product, and the vector products."""
    layers = [
        LayerDescriptor(
            layer_id="satellite",
            kind="raster",
            title="Satellite imagery",
            tile_url_template=ESRI_WORLD_IMAGERY.tile_url_template,
            source=ESRI_WORLD_IMAGERY.provider,
        )
    ]
    written = set(asset.details.get("products", ["dem", "hillshade"]))
    for product_id in PRODUCTS:
        if product_id in written:
            layers.append(raster_layer(asset, product_id, store, tiles_base))
    if asset.details.get("streams"):
        threshold_ha = float(asset.details["streams"]["threshold_area_m2"]) / 1e4
        layers.append(
            LayerDescriptor(
                layer_id="streams",
                kind="vector",
                title="Modelled streams",
                tile_url_template=f"/api/v1/terrain/{asset.village_id}/streams",
                source=f"D8 accumulation >= {threshold_ha:g} ha",
            )
        )
    layers.append(
        LayerDescriptor(
            layer_id="contours",
            kind="vector",
            title="Contours",
            tile_url_template=f"/api/v1/terrain/{asset.village_id}/contours?interval={{interval}}",
            units="m",
            value_range=[float(asset.statistics["min"]), float(asset.statistics["max"])],
            source="marching squares on the working DEM, Douglas-Peucker simplified",
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
