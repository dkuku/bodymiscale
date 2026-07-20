"""Metrics module — body-composition indices normalised by height.

These indices express a mass compartment relative to height² (kg/m²), the same
normalisation BMI uses. Unlike BMI they distinguish *what* the mass is made of,
so they stay meaningful for muscular or lean subjects where BMI is misleading.

All three reuse compartments already computed from impedance — no extra input
is required:

  FFMI : Fat-Free Mass Index    = LBM / height_m²
         VanItallie et al. 1990. Muscularity index independent of fat.
         A height-normalised FFMI (adjusted to 1.8 m) is exposed as an
         attribute; it removes the residual height bias of the raw index.

  FMI  : Fat Mass Index         = fat_mass / height_m²
         Kelly et al. 2009. The adiposity counterpart of FFMI; far more
         specific than fat% alone because it accounts for body size.

  SMI  : Skeletal Muscle Index  = skeletal_muscle_mass / height_m²
         Janssen et al. 2002 — the standard sarcopenia screening index.
         Requires dual-frequency mode (skeletal muscle mass is dual-only).
"""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from homeassistant.helpers.typing import StateType

from ..const import CONF_HEIGHT
from ..models import Metric
from ..util import check_value_constraints, to_float


def _height_m2(config: Mapping[str, Any]) -> float:
    """Return height² in m², or 0.0 if height is invalid."""
    h = to_float(config.get(CONF_HEIGHT))
    if h <= 0:
        return 0.0
    return (h / 100.0) ** 2


def get_ffmi(
    config: Mapping[str, Any], metrics: Mapping[Metric, StateType | datetime]
) -> float:
    """Calculate Fat-Free Mass Index (kg/m²).

    FFMI = LBM / height_m²   (VanItallie et al. 1990)

    A normalised FFMI (adjusted to a 1.8 m reference height) is attached as an
    attribute by the sensor layer; it is computed here for reuse:
        FFMI_norm = FFMI + 6.3 × (1.8 − height_m)
    """
    lbm = to_float(metrics.get(Metric.LBM))
    h2 = _height_m2(config)

    if lbm <= 0 or h2 <= 0:
        return 0.0

    ffmi = lbm / h2
    return check_value_constraints(ffmi, 5, 40)


def normalized_ffmi(ffmi: float, height_cm: float) -> float | None:
    """Return height-normalised FFMI (adjusted to a 1.8 m reference height).

    FFMI_norm = FFMI + 6.3 × (1.8 − height_m)   (VanItallie et al. 1990)

    Removes the residual bias that makes the raw FFMI slightly favour taller
    subjects, so values are comparable across heights. Returns ``None`` when
    inputs are invalid.
    """
    if ffmi <= 0 or height_cm <= 0:
        return None

    ffmi_norm = ffmi + 6.3 * (1.8 - height_cm / 100.0)
    return round(check_value_constraints(ffmi_norm, 5, 40), 1)


def get_fmi(
    config: Mapping[str, Any], metrics: Mapping[Metric, StateType | datetime]
) -> float:
    """Calculate Fat Mass Index (kg/m²).

    FMI = fat_mass / height_m²   (Kelly et al. 2009)
    where fat_mass = weight × fat% / 100.
    """
    w = to_float(metrics.get(Metric.WEIGHT))
    fat_pct = to_float(metrics.get(Metric.FAT_PERCENTAGE))
    h2 = _height_m2(config)

    if w <= 0 or fat_pct <= 0 or h2 <= 0:
        return 0.0

    fat_mass = w * fat_pct / 100.0
    fmi = fat_mass / h2
    return check_value_constraints(fmi, 1, 40)


def get_smi(
    config: Mapping[str, Any], metrics: Mapping[Metric, StateType | datetime]
) -> float:
    """Calculate Skeletal Muscle Index (kg/m²).

    SMI = skeletal_muscle_mass / height_m²   (Janssen et al. 2002)

    Sarcopenia screening index. Requires dual-frequency mode, which is the
    only mode that produces skeletal muscle mass.
    """
    smm = to_float(metrics.get(Metric.SKELETAL_MUSCLE_MASS))
    h2 = _height_m2(config)

    if smm <= 0 or h2 <= 0:
        return 0.0

    smi = smm / h2
    return check_value_constraints(smi, 3, 20)
