"""Infer a DEM's provenance from the text an upload carries about itself.

The sample map's ``sources`` placemark says its contours were interpolated from
SRTM (~30 m) via Mapzen terrain tiles. That single fact caps the honest
precision of every downstream number, so the system reads it rather than
ignoring it — but reads it through a *table of known datasets*, not a rule
written for this one file. A map that names ASTER or Copernicus resolves to
their published figures; a map that names nothing gets conservative defaults
and a warning that says so.

Accuracy figures are LE90 values from the datasets' own documentation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.dem import DEMProvenance


@dataclass(frozen=True, slots=True)
class _KnownDataset:
    pattern: str
    label: str
    resolution_m: float
    relative_m: float
    absolute_m: float
    attribution: str
    acquired: str | None = None


# Candidate datasets. Which one is *primary* is decided by evidence in the
# text, not by position in this table — see infer_provenance().
_KNOWN: tuple[_KnownDataset, ...] = (
    _KnownDataset(r"alos.*12\.5|palsar", "ALOS PALSAR RTC 12.5 m", 12.5, 5.0, 10.0, "JAXA ALOS"),
    _KnownDataset(
        r"copernicus|cop30|glo-?30",
        "Copernicus DEM GLO-30",
        30.0,
        2.0,
        4.0,
        "© DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018, "
        "provided under COPERNICUS by the European Union and ESA",
    ),
    _KnownDataset(
        r"srtm",
        "NASA/USGS SRTM v3 (~30 m)",
        30.0,
        6.0,
        16.0,
        "NASA/USGS SRTM",
        "2000-02 (SRTM mission)",
    ),
    _KnownDataset(r"aster", "ASTER GDEM v3", 30.0, 7.0, 17.0, "NASA/METI ASTER GDEM"),
    _KnownDataset(r"aw3d|alos", "ALOS World 3D 30 m", 30.0, 5.0, 10.0, "JAXA AW3D30"),
    _KnownDataset(r"hydrosheds", "HydroSHEDS (~90 m)", 90.0, 8.0, 16.0, "HydroSHEDS © WWF"),
    _KnownDataset(r"gmted", "USGS GMTED2010 (~250 m)", 250.0, 20.0, 40.0, "USGS GMTED2010"),
)

_ATTRIBUTION_ONLY: tuple[tuple[str, str], ...] = (
    (r"mapzen|terrain ?tiles|terraincache", "Mapzen terrain tiles"),
)


def infer_provenance(metadata_text: str, *, default_resolution_m: float) -> DEMProvenance:
    """Match the upload's own metadata against the dataset table.

    Args:
        metadata_text: Concatenated names/descriptions from the file.
        default_resolution_m: Used, with a warning, when nothing is recognised.
    """
    text = metadata_text.lower()
    # Evidence score per dataset: every mention counts once; a mention inside a
    # raw raster filename ("srtm/N21E081.tif") counts five, because a file
    # reference is the strongest statement a map can make about its own source.
    # Generic attribution blurbs name many datasets once each; the real source
    # is named repeatedly and by file. Ties go to the finer product.
    scored: list[tuple[int, _KnownDataset]] = []
    for dataset in _KNOWN:
        mentions = len(re.findall(dataset.pattern, text))
        if not mentions:
            continue
        raw_files = len(re.findall(rf"[\w/.-]*({dataset.pattern})[\w/.-]*\.tiff?\b", text))
        scored.append((mentions + 5 * raw_files, dataset))
    matched = [d for _, d in scored]
    attribution: list[str] = [d.attribution for d in matched]
    for pattern, label in _ATTRIBUTION_ONLY:
        if re.search(pattern, text):
            attribution.append(label)

    if not matched:
        return DEMProvenance(
            source="unknown — not stated in the upload",
            native_resolution_m=default_resolution_m,
            vertical_accuracy_relative_m=max(6.0, default_resolution_m / 5.0),
            vertical_accuracy_absolute_m=max(16.0, default_resolution_m / 2.0),
            attribution=tuple(dict.fromkeys(attribution)),
            assumed=True,
        )

    primary = max(scored, key=lambda item: (item[0], -item[1].resolution_m))[1]
    return DEMProvenance(
        source=primary.label,
        native_resolution_m=primary.resolution_m,
        vertical_accuracy_relative_m=primary.relative_m,
        vertical_accuracy_absolute_m=primary.absolute_m,
        attribution=tuple(dict.fromkeys(attribution)),
        acquired=primary.acquired,
    )
