"""LIA — ACCÈS DE DEHORS, l'intégration pour Home Assistant Container et Core (lot 6, 10/11).

Elle fait tourner le cœur du module (`coeur/`, le lot 4, copié par `assembler.sh`) DANS Home
Assistant : une ligne sortante vers le relais de Lia, une ligne par session, chiffrée de bout en
bout, et le pont vers le WebSocket de ce même HA. Elle ne garde aucune clé de HA : l'app envoie la
sienne, dans la session. Rien n'entre dans la maison : c'est elle qui appelle.

Ce que l'intégration ajoute au cœur : ses réglages (l'assistant, `config_flow.py`), la clé de la
maison rangée dans `.storage` de HA, l'adresse de HA au port que HA sert, et une entité qui dit si
la ligne tient et montre la clé publique du module (`binary_sensor.py`), pour que l'app l'épingle.
"""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coeur.cles import charger_ou_creer
from .coeur.module import Module
from .coeur.reglages import url_ha
from .const import CONF_JETON, CONF_RELAIS, FICHIER_CLE
from .maj import programmer

PLATFORMS = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # La clé se lit ou se crée sur le disque : hors de la boucle de HA.
    cle = await hass.async_add_executor_job(charger_ou_creer, hass.config.path(".storage", FICHIER_CLE))
    tls = bool(hass.config.api and hass.config.api.use_ssl)
    module = Module(
        relais=entry.data[CONF_RELAIS],
        jeton=entry.data[CONF_JETON],
        # Le port que HA sert vraiment, lu chez HA : jamais 8123 supposé.
        url_ha=url_ha(hass.http.server_port, tls),
        cle=cle,
        verifier_tls_ha=not tls,
    )
    entry.runtime_data = module
    # Une tâche de fond liée à l'entrée : HA l'arrête quand on retire ou recharge l'intégration.
    entry.async_create_background_task(hass, module.tourner(), "lia_relais : ligne vers le relais")
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Chaque nuit, la version publiée s'installe seule (`maj.py`).
    programmer(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await entry.runtime_data.arreter()
    return ok
