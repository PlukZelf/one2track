import asyncio
from requests import ConnectTimeout, HTTPError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from .client import get_client, One2TrackConfig
from .common import (
    CONF_USER_NAME,
    CONF_PASSWORD,
    CONF_ID,
    DOMAIN,
    LOGGER
)

PLATFORMS = ["device_tracker", "sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up One2Track Data from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    config = One2TrackConfig(username=entry.data[CONF_USER_NAME], password=entry.data[CONF_PASSWORD], id=entry.data[CONF_ID])
    api = get_client(config)
    try:
        account_id = await api.install()
    except (ConnectTimeout, HTTPError) as ex:
        LOGGER.error("Could not retrieve details from One2Track API")
        raise ConfigEntryNotReady from ex

    if account_id != entry.data[CONF_ID]:
        LOGGER.error(f"Unexpected account id: {account_id}. Expected: {entry.data[CONF_ID]}")
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = {"api_client": api}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
