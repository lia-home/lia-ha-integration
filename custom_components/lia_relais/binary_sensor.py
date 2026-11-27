"""L'entité « Lia — accès de dehors » : la ligne vers le relais tient-elle ?

Elle montre aussi la clé PUBLIQUE du module (`cle_publique`, et son `empreinte`) : l'app la lit ici,
chez HA, avec sa clé HA, et l'épingle. Elle ne vient jamais du relais ni du cloud. La clé privée ne
quitte jamais le module.
"""
from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.loader import async_get_integration

from .coeur.entite import attributs_du_module
from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(hass, entry, async_add_entities):
    # La version de `manifest.json`, lue par HA : l'app voit quelle intégration tourne.
    version = str((await async_get_integration(hass, DOMAIN)).version or "")
    async_add_entities([LigneDeDehors(entry, version)])


class LigneDeDehors(BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_should_poll = True
    _attr_name = "Lia Home"
    _attr_icon = "mdi:home-export-outline"

    def __init__(self, entry, version: str):
        self._module = entry.runtime_data
        self._version = version
        self._attr_unique_id = entry.entry_id + "-ligne"

    @property
    def is_on(self) -> bool:
        return self._module.connecte

    @property
    def extra_state_attributes(self):
        # La clé publique, `appels_web` et la version : les mêmes que l'add-on (`coeur/entite.py`).
        return attributs_du_module(self._module.cle_publique, self._version)
