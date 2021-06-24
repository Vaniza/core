"""Tests for the WLED select platform."""
import json
from unittest.mock import MagicMock

import pytest
from wled import Device as WLEDDevice, WLEDConnectionError, WLEDError

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.select.const import ATTR_OPTION, ATTR_OPTIONS
from homeassistant.components.wled.const import DOMAIN, SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ICON,
    SERVICE_SELECT_OPTION,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture


@pytest.fixture
async def enable_all(hass: HomeAssistant) -> None:
    """Enable all disabled by default select entities."""
    registry = er.async_get(hass)

    # Pre-create registry entries for disabled by default sensors
    registry.async_get_or_create(
        SELECT_DOMAIN,
        DOMAIN,
        "aabbccddeeff_palette_0",
        suggested_object_id="wled_rgb_light_color_palette",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SELECT_DOMAIN,
        DOMAIN,
        "aabbccddeeff_palette_1",
        suggested_object_id="wled_rgb_light_segment_1_color_palette",
        disabled_by=None,
    )


async def test_select_state(
    hass: HomeAssistant, enable_all: None, init_integration: MockConfigEntry
) -> None:
    """Test the creation and values of the WLED selects."""
    entity_registry = er.async_get(hass)

    # First segment of the strip
    state = hass.states.get("select.wled_rgb_light_segment_1_color_palette")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:palette-outline"
    assert state.attributes.get(ATTR_OPTIONS) == [
        "Analogous",
        "April Night",
        "Autumn",
        "Based on Primary",
        "Based on Set",
        "Beach",
        "Beech",
        "Breeze",
        "C9",
        "Cloud",
        "Cyane",
        "Default",
        "Departure",
        "Drywet",
        "Fire",
        "Forest",
        "Grintage",
        "Hult",
        "Hult 64",
        "Icefire",
        "Jul",
        "Landscape",
        "Lava",
        "Light Pink",
        "Magenta",
        "Magred",
        "Ocean",
        "Orange & Teal",
        "Orangery",
        "Party",
        "Pastel",
        "Primary Color",
        "Rainbow",
        "Rainbow Bands",
        "Random Cycle",
        "Red & Blue",
        "Rewhi",
        "Rivendell",
        "Sakura",
        "Set Colors",
        "Sherbet",
        "Splash",
        "Sunset",
        "Sunset 2",
        "Tertiary",
        "Tiamat",
        "Vintage",
        "Yelblu",
        "Yellowout",
        "Yelmag",
    ]
    assert state.state == "Random Cycle"

    entry = entity_registry.async_get("select.wled_rgb_light_segment_1_color_palette")
    assert entry
    assert entry.unique_id == "aabbccddeeff_palette_1"


async def test_segment_change_state(
    hass: HomeAssistant,
    enable_all: None,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test the option change of state of the WLED segments."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.wled_rgb_light_segment_1_color_palette",
            ATTR_OPTION: "Some Other Palette",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.segment.call_count == 1
    mock_wled.segment.assert_called_with(
        segment_id=1,
        palette="Some Other Palette",
    )


@pytest.mark.parametrize("mock_wled", ["wled/rgb_single_segment.json"], indirect=True)
async def test_dynamically_handle_segments(
    hass: HomeAssistant,
    enable_all: None,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test if a new/deleted segment is dynamically added/removed."""
    segment0 = hass.states.get("select.wled_rgb_light_color_palette")
    segment1 = hass.states.get("select.wled_rgb_light_segment_1_color_palette")
    assert segment0
    assert segment0.state == "Default"
    assert not segment1

    return_value = mock_wled.update.return_value
    mock_wled.update.return_value = WLEDDevice(
        json.loads(load_fixture("wled/rgb.json"))
    )

    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    segment0 = hass.states.get("select.wled_rgb_light_color_palette")
    segment1 = hass.states.get("select.wled_rgb_light_segment_1_color_palette")
    assert segment0
    assert segment0.state == "Default"
    assert segment1
    assert segment1.state == "Random Cycle"

    # Test adding if segment shows up again, including the master entity
    mock_wled.update.return_value = return_value
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    segment0 = hass.states.get("select.wled_rgb_light_color_palette")
    segment1 = hass.states.get("select.wled_rgb_light_segment_1_color_palette")
    assert segment0
    assert segment0.state == "Default"
    assert segment1
    assert segment1.state == STATE_UNAVAILABLE


async def test_select_error(
    hass: HomeAssistant,
    enable_all: None,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling of the WLED selects."""
    mock_wled.segment.side_effect = WLEDError

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.wled_rgb_light_segment_1_color_palette",
            ATTR_OPTION: "Whatever",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("select.wled_rgb_light_segment_1_color_palette")
    assert state
    assert state.state == "Random Cycle"
    assert "Invalid response from API" in caplog.text
    assert mock_wled.segment.call_count == 1
    mock_wled.segment.assert_called_with(segment_id=1, palette="Whatever")


async def test_select_connection_error(
    hass: HomeAssistant,
    enable_all: None,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling of the WLED selects."""
    mock_wled.segment.side_effect = WLEDConnectionError

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.wled_rgb_light_segment_1_color_palette",
            ATTR_OPTION: "Whatever",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("select.wled_rgb_light_segment_1_color_palette")
    assert state
    assert state.state == STATE_UNAVAILABLE
    assert "Error communicating with API" in caplog.text
    assert mock_wled.segment.call_count == 1
    mock_wled.segment.assert_called_with(segment_id=1, palette="Whatever")


@pytest.mark.parametrize(
    "entity_id",
    (
        "select.wled_rgb_light_color_palette",
        "select.wled_rgb_light_segment_1_color_palette",
    ),
)
async def test_disabled_by_default_selects(
    hass: HomeAssistant, init_integration: MockConfigEntry, entity_id: str
) -> None:
    """Test the disabled by default WLED selects."""
    registry = er.async_get(hass)

    state = hass.states.get(entity_id)
    assert state is None

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.disabled
    assert entry.disabled_by == er.DISABLED_INTEGRATION