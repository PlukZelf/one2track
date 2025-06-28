import logging
from datetime import timedelta, datetime
from typing import List

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import async_timeout
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.zone import async_active_zone
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .client import GpsClient, TrackerDevice
from .common import (
    DOMAIN, DEFAULT_UPDATE_RATE_SEC
)

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Add an entry."""
    LOGGER.debug("one2track async_setup_entry")

    gps_api: GpsClient = hass.data[DOMAIN][entry.entry_id]['api_client']
    devices: List[TrackerDevice] = await gps_api.update()

    coordinator = GpsCoordinator(hass, gps_api, True)

    LOGGER.info("Adding %s found one2track devices", len(devices))

    for device in devices:
        LOGGER.debug("Adding %s", device)
        async_add_entities(
            [
                One2TrackSensor(
                    coordinator,
                    hass,
                    entry,
                    device
                )
            ],
            update_before_add=True,
        )

    LOGGER.debug("Done adding all trackers.")


class GpsCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, gps_api: GpsClient, first_boot):
        super().__init__(
            hass,
            LOGGER,
            name="One2Track",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_RATE_SEC),
            always_update=False
        )
        self.gps_api = gps_api
        self.first_boot = first_boot
        self.last_update = None

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            async with async_timeout.timeout(300):
                data = await self.gps_api.update()
                LOGGER.debug("Update from the coordinator %s", data)

                update = True
                if update or self.first_boot:
                    LOGGER.debug("Updating sensor data. Last update: %s", self.last_update)
                    self.last_update = datetime.now()
                    return data
                else:
                    LOGGER.debug("No new data to enter")
                    return None

        except Exception as err:
            LOGGER.error("Error in updating updater")
            LOGGER.error(err)
            raise UpdateFailed(err)


class One2TrackSensor(CoordinatorEntity, TrackerEntity):
    _device: TrackerDevice

    def __init__(
            self,
            coordinator,
            hass: HomeAssistant,
            entry: ConfigEntry,
            device: TrackerDevice
    ) -> None:
        super().__init__(coordinator)
        self._hass = hass
        self._entry = entry
        self._device = device
        self._attr_unique_id = device['uuid']
        self._attr_name = f"one2track_{device['name']}"
        self._zone_name = None  # cache for zone name

    @property
    def name(self):
        return self._device['name']

    @property
    def source_type(self):
        return "gps"  # TODO: Could be router when status=WIFI

    def async_device_changed(self):
        LOGGER.debug("%s (%s) advising HA of update", self.name, self.unique_id)
        self.async_schedule_update_ha_state()

    @property
    def location_accuracy(self):
        return 10  # TODO check signal strength

    @property
    def should_poll(self):
        return False

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "serial_number": self._device['serial_number'],
            "name": self._device['name']
        }

    @property
    def icon(self):
        return "mdi:watch-variant"

    @property
    def extra_state_attributes(self):
        return {
            "serial_number": self._device['serial_number'],
            "uuid": self._device['uuid'],
            "name": self._device['name'],

            "status": self._device['status'],
            "phone_number": self._device['phone_number'],
            "tariff_type": self._device['simcard']['tariff_type'],
            "balance_cents": self._device['simcard']['balance_cents'],

            "last_communication": self._device['last_location']['last_communication'],
            "last_location_update": self._device['last_location']['last_location_update'],
            "altitude": self._device['last_location']['altitude'],
            "location_type": self._device['last_location']['location_type'],
            "address": self._device['last_location']['address'],
            "signal_strength": self._device['last_location']['signal_strength'],
            "satellite_count": self._device['last_location']['satellite_count'],
            "host": self._device['last_location']['host'],
            "port": self._device['last_location']['port'],
        }

    @property
    def battery_level(self):
        return self._device["last_location"]["battery_percentage"]

    @property
    def location_name(self):
        if self._device["last_location"]["location_type"] == 'WIFI':
            return 'home'

        if self._zone_name:
            return self._zone_name

        return self._device['last_location']['address']

    @property
    def latitude(self):
        return float(self._device['last_location']['latitude'])

    @property
    def longitude(self):
        return float(self._device['last_location']['longitude'])

    @property
    def unique_id(self):
        return self._device['uuid']

    async def _async_update_zone(self):
        """Async update zone name based on current lat/lon."""
        try:
            zone = await async_active_zone(self._hass, self.latitude, self.longitude)
            if zone:
                self._zone_name = zone.name
            else:
                self._zone_name = None
        except Exception as err:
            LOGGER.error(f"Cannot get zone for tracker: {err}")
            self._zone_name = None

    @callback
    def _update_from_latest_data(self) -> None:
        new_data: List[TrackerDevice] = self.coordinator.data
        me = next((x for x in new_data if x['uuid'] == self.unique_id), None)
        if me:
            self._device = me
        else:
            LOGGER.error(f"Tracker {self.unique_id} not found in new data: {new_data}")

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_from_latest_data()
        self.async_schedule_update_ha_state()
        self._hass.async_create_task(self._async_update_zone())

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self):
        await super().async_will_remove_from_hass()
