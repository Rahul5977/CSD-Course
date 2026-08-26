from app.providers.dem_provenance import infer_provenance


def test_the_dataset_named_by_file_and_most_often_is_primary() -> None:
    """A generic attribution list names Copernicus once; the raw raster is SRTM."""
    text = (
        "SRTM terrain data courtesy of NASA. Approximate resolution about 30 m. "
        "Raw source raster references: srtm/N21E081.tif, gmted/10N060E.tif. "
        "EU-DEM produced using Copernicus data. HydroSHEDS. Mapzen terrain tiles."
    )
    p = infer_provenance(text, default_resolution_m=10.0)
    assert p.native_resolution_m == 30.0
    assert "SRTM" in p.source
    assert p.assumed is False
    assert "Mapzen terrain tiles" in p.attribution and "HydroSHEDS © WWF" in p.attribution


def test_unknown_source_is_flagged_as_assumed() -> None:
    p = infer_provenance("Contours by Surveyor X", default_resolution_m=10.0)
    assert p.assumed is True
    assert p.native_resolution_m == 10.0


def test_copernicus_is_recognised() -> None:
    assert infer_provenance("Copernicus GLO-30", default_resolution_m=10).source.startswith(
        "Copernicus"
    )


def test_a_finer_product_wins_only_on_equal_evidence() -> None:
    p = infer_provenance("SRTM and Copernicus GLO-30 composite", default_resolution_m=10)
    assert p.source.startswith("Copernicus"), "one mention each -> the finer product"
