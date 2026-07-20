"""Tests for skeletal muscle mass across impedance modes.

- dual     → Janssen BIA on the 50 kHz (low-frequency) reading
- standard → Janssen BIA on the single impedance reading
- none     → Lee-2000 anthropometric estimate (no impedance needed)
"""

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
from custom_components.bodymiscale.models import Gender, Metric


def _make_config(
    *,
    height: float = 180.0,
    gender: Gender = Gender.MALE,
    birthday: str = "1990-03-10",
    impedance_mode: str = IMPEDANCE_MODE_NONE,
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


async def test_smm_standard_mode_uses_janssen(hass: HomeAssistant) -> None:
    """Standard single-impedance scales compute SMM via Janssen."""
    config = _make_config(
        impedance_mode=IMPEDANCE_MODE_STANDARD,
        weight_sensor="sensor.w_smm_std",
        impedance_sensor="sensor.imp_smm_std",
    )
    handler = BodyScaleMetricsHandler(hass, config, config_entry_id="smm_std")

    smm: list[float] = []
    handler.subscribe(Metric.SKELETAL_MUSCLE_MASS, lambda v: smm.append(float(v)))

    hass.states.async_set("sensor.w_smm_std", "80.0")
    await hass.async_block_till_done()
    assert not smm, "Standard mode SMM must wait for the impedance reading"

    hass.states.async_set("sensor.imp_smm_std", "500")
    await hass.async_block_till_done()
    assert smm and 20 < smm[-1] < 45
    handler.unload()


async def test_smm_no_impedance_uses_lee(hass: HomeAssistant) -> None:
    """No-impedance (Gen1) scales compute SMM from the Lee anthropometric model."""
    config = _make_config(
        impedance_mode=IMPEDANCE_MODE_NONE,
        weight_sensor="sensor.w_smm_none",
    )
    handler = BodyScaleMetricsHandler(hass, config, config_entry_id="smm_none")

    smm: list[float] = []
    handler.subscribe(Metric.SKELETAL_MUSCLE_MASS, lambda v: smm.append(float(v)))

    # Weight alone is enough — Lee needs no impedance.
    hass.states.async_set("sensor.w_smm_none", "80.0")
    await hass.async_block_till_done()
    assert smm and 25 < smm[-1] < 45
    handler.unload()


async def test_smm_dual_mode_uses_janssen(hass: HomeAssistant) -> None:
    """Dual scales still compute SMM via Janssen once both impedances arrive."""
    config = _make_config(
        height=175.0,
        impedance_mode=IMPEDANCE_MODE_DUAL,
        weight_sensor="sensor.w_smm_dual",
        impedance_low_sensor="sensor.imp_low_smm",
        impedance_high_sensor="sensor.imp_high_smm",
    )
    handler = BodyScaleMetricsHandler(hass, config, config_entry_id="smm_dual")

    smm: list[float] = []
    handler.subscribe(Metric.SKELETAL_MUSCLE_MASS, lambda v: smm.append(float(v)))

    hass.states.async_set("sensor.w_smm_dual", "75.0")
    hass.states.async_set("sensor.imp_low_smm", "300")
    await hass.async_block_till_done()
    assert not smm, "Dual mode SMM needs both impedance frequencies"

    hass.states.async_set("sensor.imp_high_smm", "250")
    await hass.async_block_till_done()
    assert smm and smm[-1] > 0
    handler.unload()
