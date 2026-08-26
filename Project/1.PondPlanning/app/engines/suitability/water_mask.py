"""Surface water from Sentinel-2 with NDWI + OpenCV clean-up (FR3 buffer input).

**NDWI** (McFeeters 1996) = (Green - NIR) / (Green + NIR): open water is
strongly positive, vegetation and soil negative. The threshold is not fixed
but found by **Otsu's method** (``cv2.threshold(..., THRESH_OTSU)``) on the
NDWI histogram, so it adapts to each scene. The binary mask is then cleaned
with **morphological opening and closing** (``cv2.morphologyEx``) to drop
single-pixel noise and fill small holes, and **connected components**
(``cv2.connectedComponentsWithStats``) reject blobs under ``min_area_m2``.

Two composites — pre-monsoon (Mar-May) and post-monsoon (Oct-Dec) —
separate *perennial* water (present in both) from *seasonal* water.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class WaterMask:
    """A cleaned water mask and the numbers behind it."""

    mask: NDArray[np.bool_]
    ndwi: NDArray[np.float64]
    otsu_threshold: float
    components_before: int
    components_after: int
    water_fraction: float


def ndwi(green: NDArray[np.floating], nir: NDArray[np.floating]) -> NDArray[np.float64]:
    """McFeeters NDWI; NaN where both bands are zero (no data)."""
    g = green.astype(np.float64)
    n = nir.astype(np.float64)
    denominator = g + n
    with np.errstate(invalid="ignore", divide="ignore"):
        index = np.where(denominator > 0, (g - n) / denominator, np.nan)
    return np.asarray(index, dtype=np.float64)


def water_mask_from_ndwi(
    index: NDArray[np.float64],
    *,
    pixel_size_m: float,
    min_area_m2: float = 200.0,
    kernel_px: int = 3,
) -> WaterMask:
    """Otsu threshold → open/close → drop small components."""
    valid = ~np.isnan(index)
    scaled = np.zeros(index.shape, dtype=np.uint8)
    scaled[valid] = np.clip((index[valid] + 1.0) * 127.5, 0, 255).astype(np.uint8)
    # Otsu on valid pixels only; OpenCV needs a full image, so fill nodata with the valid mean.
    fill = int(scaled[valid].mean()) if valid.any() else 0
    scaled[~valid] = fill
    threshold_u8, thresholded = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    binary = np.asarray(thresholded, dtype=np.uint8)
    otsu = float(np.asarray(threshold_u8).item()) / 127.5 - 1.0
    # NDWI water must also be positive: guards against a bimodal land-only scene
    # (Otsu then splits land in two and the wetter half would be called water).
    if otsu < 0.0:
        otsu = 0.0
        binary = np.asarray((index > 0.0) & valid, dtype=np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_px, kernel_px))
    opened = np.asarray(cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel), dtype=np.uint8)
    closed = np.asarray(cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel), dtype=np.uint8)
    n_before, _, _, _ = cv2.connectedComponentsWithStats(
        np.asarray(binary > 0, dtype=np.uint8), connectivity=8
    )
    n_after, labels, stats, _ = cv2.connectedComponentsWithStats(
        np.asarray(closed > 0, dtype=np.uint8), connectivity=8
    )
    min_px = max(1, round(min_area_m2 / (pixel_size_m**2)))
    keep = np.zeros(n_after, dtype=bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= min_px
    mask = np.asarray(keep[labels] & valid, dtype=bool)
    return WaterMask(
        mask=mask,
        ndwi=index,
        otsu_threshold=float(otsu),
        components_before=int(n_before - 1),
        components_after=int(keep.sum()),
        water_fraction=float(mask[valid].mean()) if valid.any() else 0.0,
    )


def combine_seasons(
    pre: NDArray[np.bool_], post: NDArray[np.bool_]
) -> tuple[NDArray[np.bool_], NDArray[np.bool_]]:
    """``(perennial, seasonal)``: water in both composites vs post-monsoon only."""
    return pre & post, post & ~pre
