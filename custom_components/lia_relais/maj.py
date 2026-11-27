"""La mise à jour seule de l'intégration, chaque nuit (27/11) : la colle avec HA de `coeur/mise_a_jour.py`.

Chaque nuit à 3 h (minute fixe par maison), lire la dernière version publiée sur GitHub ; si elle passe
devant celle qui tourne, `update.install` sur l'entité du magasin (HACS ou Marketplace), puis
`homeassistant.restart`. Tout refus se rejoue la nuit suivante ; l'app reste le recours.
"""
import logging

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change
from homeassistant.loader import async_get_integration

from .coeur import mise_a_jour as maj
from .const import DOMAIN

JOURNAL = logging.getLogger(__name__)


async def nuit(hass: HomeAssistant, url: str = maj.URL_DERNIERE, depots=maj.DEPOTS) -> str:
    """Une nuit, tout de suite : ce que fait le réveil de 3 h (le banc l'appelle aussi)."""
    version = str((await async_get_integration(hass, DOMAIN)).version or "")

    async def lire_publiee():
        async with async_get_clientsession(hass).get(
                url, headers={"Accept": "application/vnd.github+json"},
                timeout=aiohttp.ClientTimeout(total=30)) as r:
            r.raise_for_status()
            return (await r.json()).get("tag_name")

    def lire_etats():
        return [{"entity_id": e.entity_id, "attributes": dict(e.attributes)} for e in hass.states.async_all("update")]

    async def installer(entite, publiee):
        JOURNAL.info("version %s publiée : le magasin l'installe (%s)", publiee, entite)
        await hass.services.async_call("update", "install", {"entity_id": entite, "version": publiee}, blocking=True)

    async def redemarrer():
        JOURNAL.info("Home Assistant redémarre pour charger la version neuve")
        await hass.services.async_call("homeassistant", "restart", {}, blocking=False)

    issue = await maj.la_nuit(version_installee=version, lire_publiee=lire_publiee, lire_etats=lire_etats,
                              installer=installer, redemarrer=redemarrer, depots=depots)
    JOURNAL.info("mise à jour de la nuit : %s (version %s)", issue, version)
    return issue


def programmer(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Le réveil de chaque nuit, arrêté avec l'entrée."""
    async def reveil(_maintenant):
        await nuit(hass)

    entry.async_on_unload(async_track_time_change(
        hass, reveil, hour=maj.HEURE, minute=maj.minute_de_la_nuit(entry.entry_id), second=0))
