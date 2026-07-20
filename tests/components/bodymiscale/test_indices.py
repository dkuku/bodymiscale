"""Tests for bodymiscale metrics/indices.py (FFMI, FMI, SMI)."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from custom_components.bodymiscale.const import (
    CONF_BIRTHDAY,
    CONF_CALCULATION_MODE,
    CONF_GENDER,
    CONF_HEIGHT,
    CONF_IMPEDANCE_MODE,
    CONF_PROFILE_METHOD,
    CONF_SENSOR_IMPEDANCE,
    CONF_SENSOR_IMPEDANCE_HIGH,
    CONF_SENSOR_IMPEDANCE_LOW,
    CONF_SENSOR_WEIGHT,
    IMPEDANCE_MODE_DUAL,
    IMPEDANCE_MODE_NONE,
    IMPEDANCE_MODE_STANDARD,
    PROFILE_METHOD_NONE,
)
from custom_components.bodymiscale.metrics import BodyScaleMetricsHandler
from custom_components.bodymiscale.metrics.indices import normalized_ffmi
from custom_components.bodymiscale.models import Gender, Metric


def _make_config(
    *,
    height: float = 175.0,
    gender: Gender = Gender.MALE,
    birthday: str = "1990-03-10",
    impedance_mode: str = IMPEDANCE_MODE_STANDARD,
    weight_sensor: str = "sensor.weight",
    impedance_sensor: str | None = None,
    impedance_low_sensor: str | None = None,
    impedance_high_sensor: str | None = None,
) -> dict[str, Any]:
    config: dict[str, Any] = {
        "name": "TestUser",
        CONF_BIRTHDAY: birthday,
        CONF_GENDER: gender,
        CONF_HEIGHT: height,
        CONF_CALCULATION_MODE: "science",
        CONF_IMPEDANCE_MODE: impedance_mode,
        CONF_PROFILE_METHOD: PROFILE_METHOD_NONE,
        CONF_SENSOR_WEIGHT: weight_sensor,
    }
    if impedance_sensor:
        config[CONF_SENSOR_IMPEDANCE] = impedance_sensor
    if impedance_low_sensor:
        config[CONF_SENSOR_IMPEDANCE_LOW] = impedance_low_sensor
    if impedance_high_sensor:
        config[CONF_SENSOR_IMPEDANCE_HIGH] = impedance_high_sensor
    return config


# ===========================================================================
# FFMI / FMI — standard impedance mode
# ===========================================================================


async def test_ffmi_and_fmi_computed_in_standard_mode(hass: HomeAssistant) -> None:
    """FFMI and FMI must be computed once weight + impedance are available."""
    config = _make_config(
        height=180.0,
        gender=Gender.MALE,
        impedance_mode=IMPEDANCE_MODE_STANDARD,
        weight_sensor="sensor.w_idx",
        impedance_sensor="sensor.imp_idx",
    )
    handler = BodyScaleMetricsHandler(hass, config, config_entry_id="idx_std")

    ffmi: list[float] = []
    fmi: list[float] = []
    handler.subscribe(Metric.FFMI, lambda v: ffmi.append(float(v)))
    handler.subscribe(Metric.FMI, lambda v: fmi.append(float(v)))

    hass.states.async_set("sensor.w_idx", "80.0")
    hass.states.async_set("sensor.imp_idx", "500")
    await hass.async_block_till_done()

    assert ffmi, "FFMI should be computed with standard impedance"
    assert fmi, "FMI should be computed with standard impedance"
    # Plausible ranges for an 80 kg / 1.80 m adult male
    assert 15 < ffmi[-1] < 25
    assert 2 < fmi[-1] < 12
    handler.unload()


async def test_indices_not_computed_without_impedance(hass: HomeAssistant) -> None:
    """FFMI/FMI require impedance-derived data — weight alone is not enough."""
    config = _make_config(
        impedance_mode=IMPEDANCE_MODE_NONE,
        weight_sensor="sensor.w_noimp_idx",
    )
    handler = BodyScaleMetricsHandler(hass, config, config_entry_id="idx_none")

    ffmi: list[float] = []
    fmi: list[float] = []
    handler.subscribe(Metric.FFMI, lambda v: ffmi.append(float(v)))
    handler.subscribe(Metric.FMI, lambda v: fmi.append(float(v)))

    hass.states.async_set("sensor.w_noimp_idx", "80.0")
    await hass.async_block_till_done()

    assert not ffmi
    assert not fmi
    handler.unload()


# ===========================================================================
# Skeletal muscle mass & SMI — every mode
# ===========================================================================


async def test_smi_computed_in_dual_mode(hass: HomeAssistant) -> None:
    """SMI must be computed in dual mode once both impedances are available."""
    config = _make_config(
        height=175.0,
        gender=Gender.MALE,
        impedance_mode=IMPEDANCE_MODE_DUAL,
        weight_sensor="sensor.w_smi",
        impedance_low_sensor="sensor.imp_low_smi",
        impedance_high_sensor="sensor.imp_high_smi",
    )
    handler = BodyScaleMetricsHandler(hass, config, config_entry_id="idx_dual")

    smi: list[float] = []
    handler.subscribe(Metric.SMI, lambda v: smi.append(float(v)))

    hass.states.async_set("sensor.w_smi", "75.0")
    hass.states.async_set("sensor.imp_low_smi", "300")
    await hass.async_block_till_done()
    assert not smi, "SMI needs both impedance frequencies"

    hass.states.async_set("sensor.imp_high_smi", "250")
    await hass.async_block_till_done()
    assert smi, "SMI should be computed when both impedances are available"
    assert 5 < smi[-1] <= 20
    handler.unload()


async def test_smm_smi_standard_mode_uses_janssen(hass: HomeAssistant) -> None:
    """Standard single-impedance scales get SMM/SMI via Janssen."""
    config = _make_config(
        height=180.0,
        gender=Gender.MALE,
        impedance_mode=IMPEDANCE_MODE_STANDARD,
        weight_sensor="sensor.w_smm_std",
        impedance_sensor="sensor.imp_smm_std",
    )
    handler = BodyScaleMetricsHandler(hass, config, config_entry_id="idx_std_smm")

    smm: list[float] = []
    smi: list[float] = []
    handler.subscribe(Metric.SKELETAL_MUSCLE_MASS, lambda v: smm.append(float(v)))
    handler.subscribe(Metric.SMI, lambda v: smi.append(float(v)))

    # Weight alone is not enough in an impedance mode — needs the reading.
    hass.states.async_set("sensor.w_smm_std", "80.0")
    await hass.async_block_till_done()
    assert not smm, "Standard mode SMM must wait for the impedance reading"

    hass.states.async_set("sensor.imp_smm_std", "500")
    await hass.async_block_till_done()
    assert smm and 20 < smm[-1] < 45
    assert smi and 5 < smi[-1] < 15
    handler.unload()


async def test_smm_smi_no_impedance_uses_lee(hass: HomeAssistant) -> None:
    """No-impedance (Gen1) scales get SMM/SMI from the Lee anthropometric model."""
    config = _make_config(
        height=180.0,
        gender=Gender.MALE,
        impedance_mode=IMPEDANCE_MODE_NONE,
        weight_sensor="sensor.w_smm_none",
    )
    handler = BodyScaleMetricsHandler(hass, config, config_entry_id="idx_none_smm")

    smm: list[float] = []
    smi: list[float] = []
    handler.subscribe(Metric.SKELETAL_MUSCLE_MASS, lambda v: smm.append(float(v)))
    handler.subscribe(Metric.SMI, lambda v: smi.append(float(v)))

    # Weight alone is enough — Lee needs no impedance.
    hass.states.async_set("sensor.w_smm_none", "80.0")
    await hass.async_block_till_done()
    assert smm and 25 < smm[-1] < 45
    assert smi and 5 < smi[-1] < 15
    handler.unload()


# ===========================================================================
# normalized_ffmi helper
# ===========================================================================


def test_normalized_ffmi_reference_height() -> None:
    """At exactly 1.80 m the normalised FFMI equals the raw FFMI."""
    assert normalized_ffmi(20.0, 180.0) == 20.0


def test_normalized_ffmi_adjusts_for_height() -> None:
    """Shorter subjects get a positive adjustment, taller a negative one."""
    assert normalized_ffmi(20.0, 170.0) > 20.0
    assert normalized_ffmi(20.0, 190.0) < 20.0


def test_normalized_ffmi_invalid_inputs() -> None:
    """Invalid inputs return None."""
    assert normalized_ffmi(0.0, 180.0) is None
    assert normalized_ffmi(20.0, 0.0) is None
