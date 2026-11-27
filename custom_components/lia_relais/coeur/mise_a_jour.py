"""LA MISE À JOUR SEULE DE L'INTÉGRATION, LA NUIT (27/11, décision du propriétaire).

Le propriétaire publie une version (une « release » GitHub du dépôt public) quand il le décide ; chaque
maison la prend seule, la nuit, sans l'app ni le client. Comme un pont Hue ou une box Homey.

L'intégration ne se télécharge pas elle-même : elle demande au magasin de la maison (HACS, ou la
Marketplace dès HA 2026.11) d'installer la version publiée, par le service standard
`update.install` sur l'entité de mise à jour que le magasin tient pour notre dépôt, avec `version`
(les deux magasins l'acceptent : `SPECIFIC_VERSION`, lu dans HACS 2.0.5 et HA 2026.11.2). Le magasin
n'a donc pas besoin d'avoir relu GitHub : la Marketplace ne relit un dépôt personnalisé que toutes
les 48 h. Puis HA redémarre, pour charger la version neuve.

L'add-on (HA OS) n'en a pas besoin : il demande au Supervisor sa mise à jour automatique
(`addon/lia_addon.py`).

Ce fichier ne dépend pas de HA : l'intégration lui passe de quoi lire et agir (`maj.py`).
"""
import hashlib
import re
from typing import Awaitable, Callable, Iterable, List, Optional

# Le dépôt public et ses anciens noms (GitHub redirige, mais le magasin garde le nom d'installation).
DEPOTS = ("lia-home/lia-ha-integration", "Aziz5706/lia-ha-integration")
# La dernière version publiée (hors préversions), lue sans compte : une requête par nuit et par maison.
URL_DERNIERE = "https://api.github.com/repos/lia-home/lia-ha-integration/releases/latest"
# L'heure de la nuit : HA redémarre (une minute environ), personne ne s'en sert à cette heure-là.
HEURE = 3

_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")

# Ce que la nuit a fait, pour le journal et les tests.
A_JOUR = "a_jour"
SANS_VERSION = "sans_version"      # GitHub muet ou illisible : la nuit suivante
SANS_MAGASIN = "sans_magasin"      # aucune entité de mise à jour pour notre dépôt (installé à la main)
INSTALLEE = "installee"            # le magasin a installé, HA redémarre
REDEMARRAGE = "redemarrage"        # déjà téléchargée, il manquait le redémarrage
ECHEC = "echec"                    # le magasin a refusé : la nuit suivante (l'app reste le recours)


def lire_version(texte) -> Optional[tuple]:
    """« 0.3.1 » ou « v0.3.1 » → (0, 3, 1) ; tout le reste → None (jamais comparé)."""
    m = _VERSION.match(texte.strip()) if isinstance(texte, str) else None
    return tuple(int(x) for x in m.groups()) if m else None


def plus_recente(publiee, installee) -> bool:
    """Vrai seulement si les deux se lisent et que la publiée passe devant : jamais de retour arrière."""
    p, i = lire_version(publiee), lire_version(installee)
    return p is not None and i is not None and p > i


def minute_de_la_nuit(cle: str) -> int:
    """Une minute fixe par maison, entre 0 et 59 : les maisons ne demandent pas GitHub toutes ensemble."""
    return hashlib.sha256(cle.encode("utf-8")).digest()[0] % 60


def entite_du_depot(etats: Iterable[dict], depots: Iterable[str] = DEPOTS) -> Optional[dict]:
    """L'entité `update.*` du magasin pour notre dépôt, reconnue à son `release_url` (github.com/<dépôt>/…).

    `etats` : des {"entity_id", "attributes"}. Le nom de l'entité dépend du nom affiché et de la langue :
    seul le lien vers le dépôt est sûr.
    """
    racines = ["https://github.com/%s" % d.lower() for d in depots]
    for e in etats:
        if not str(e.get("entity_id", "")).startswith("update."):
            continue
        lien = str((e.get("attributes") or {}).get("release_url") or "").lower()
        if any(lien == r or lien.startswith(r + "/") for r in racines):
            return e
    return None


async def la_nuit(*, version_installee: str,
                  lire_publiee: Callable[[], Awaitable[Optional[str]]],
                  lire_etats: Callable[[], List[dict]],
                  installer: Callable[[str, str], Awaitable[None]],
                  redemarrer: Callable[[], Awaitable[None]],
                  depots: Iterable[str] = DEPOTS) -> str:
    """Une nuit : la version publiée passe devant celle qui tourne ? Le magasin l'installe, HA redémarre.

    `version_installee` : celle du manifeste qui TOURNE (pas celle que le magasin a téléchargée).
    `installer(entite, version)` lève si le magasin refuse.
    """
    try:
        publiee = await lire_publiee()
    except Exception:  # noqa: BLE001 — réseau, GitHub, JSON : tout se rejoue la nuit suivante
        return SANS_VERSION
    if lire_version(publiee) is None:
        return SANS_VERSION
    if not plus_recente(publiee, version_installee):
        return A_JOUR
    entite = entite_du_depot(lire_etats(), depots)
    if entite is None:
        return SANS_MAGASIN
    telechargee = (entite.get("attributes") or {}).get("installed_version")
    if lire_version(telechargee) == lire_version(publiee):
        # Le magasin l'a déjà (une nuit précédente, ou la main) : il ne manque que le redémarrage.
        await redemarrer()
        return REDEMARRAGE
    try:
        await installer(entite["entity_id"], publiee.strip())
    except Exception:  # noqa: BLE001 — refus du magasin (GitHub limité, avertissement…) : la nuit suivante
        return ECHEC
    await redemarrer()
    return INSTALLEE
