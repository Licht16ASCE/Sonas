"""
Villes de la République Démocratique du Congo (RDC).

Source principale : API CountriesNow (https://countriesnow.space)
Repli : liste officielle des principales villes RDC pour la démo hors-ligne.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_KEY = 'sonas_villes_rdc_v1'
CACHE_TTL = 60 * 60 * 24  # 24 h

COUNTRIESNOW_URL = 'https://countriesnow.space/api/v0.1/countries/cities'
# CountriesNow n'expose la RDC que sous le libellé « Congo » (pas le nom complet).
# On filtre ensuite les villes typiques de la ROC (Brazzaville).
API_COUNTRY_NAMES = ('Congo',)

# Villes typiques de la République du Congo (Brazzaville) à exclure du mélange API.
ROC_EXCLUDE = {
    'brazzaville', 'pointe-noire', 'pointe noire', 'dolisie', 'nkayi', 'ouesso',
    'owando', 'sibiti', 'madingou', 'kinkala', 'mossendjo', 'loandjili',
    'djambala', 'gamboma', 'impfondo', 'ewo', 'makoua', 'kayes', 'sembé',
    'sembe', 'ouisso',
}

# Principales villes réelles de la RDC (fallback + enrichissement).
VILLES_RDC_FALLBACK = [
    'Kinshasa',
    'Lubumbashi',
    'Mbuji-Mayi',
    'Kananga',
    'Kisangani',
    'Bukavu',
    'Goma',
    'Kolwezi',
    'Likasi',
    'Tshikapa',
    'Kikwit',
    'Uvira',
    'Bunia',
    'Mbandaka',
    'Matadi',
    'Butembo',
    'Kalemie',
    'Kindu',
    'Isiro',
    'Gandajika',
    'Bandundu',
    'Gemena',
    'Mwene-Ditu',
    'Kabinda',
    'Kamina',
    'Boma',
    'Beni',
    'Baraka',
    'Kasongo',
    'Ilebo',
    'Inongo',
    'Lisala',
    'Boende',
    'Kenge',
    'Fungurume',
    'Kipushi',
    'Lodja',
    'Kabalo',
    'Kongolo',
    'Bumba',
    'Aketi',
    'Buta',
    'Gbadolite',
    'Zongo',
    'Moanda',
    'Muanda',
    'Banana',
    'Kasangulu',
    'Mbanza-Ngungu',
    'Inkisi',
    'Tshela',
    'Idiofa',
    'Bulungu',
    'Gungu',
    'Dibaya',
    'Luebo',
    'Mweka',
    'Demba',
    'Lusambo',
    'Kabongo',
    'Manono',
    'Pweto',
    'Kasenga',
    'Sakania',
    'Walikale',
    'Masisi',
    'Rutshuru',
    'Nyiragongo',
    'Kalehe',
    'Shabunda',
    'Fizi',
    'Kalima',
    'Punia',
    'Lubutu',
    'Watsa',
    'Aru',
    'Mahagi',
    'Djugu',
    'Irumu',
    'Moba',
    'Nyunzu',
    'Kabambare',
]


def _http_post_json(url: str, payload: dict, timeout: int = 15) -> dict | None:
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=body,
        method='POST',
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'SONAS-Demo/1.0 (Django; RDC cities)',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning('API villes RDC indisponible (%s): %s', payload.get('country'), exc)
        return None


def _normalize_city(name: str) -> str:
    return ' '.join((name or '').strip().split())


def _is_rdc_city(name: str) -> bool:
    key = _normalize_city(name).lower().replace('é', 'e').replace('è', 'e')
    if key in ROC_EXCLUDE:
        return False
    return True


def _fetch_from_api() -> list[str]:
    collected: set[str] = set()
    for country in API_COUNTRY_NAMES:
        data = _http_post_json(COUNTRIESNOW_URL, {'country': country})
        if not data or data.get('error'):
            continue
        for raw in data.get('data') or []:
            city = _normalize_city(str(raw))
            if city and _is_rdc_city(city):
                collected.add(city)
    return sorted(collected, key=lambda c: c.casefold())


def get_villes_rdc(*, force_refresh: bool = False) -> list[str]:
    """
    Retourne la liste des villes RDC (API + fallback fusionnés).
    Résultat mis en cache Django.
    """
    if not force_refresh:
        cached = cache.get(CACHE_KEY)
        if cached:
            return cached

    api_cities = _fetch_from_api()
    merged = {c: None for c in VILLES_RDC_FALLBACK}
    for city in api_cities:
        # Conserve la casse du fallback si doublon
        if city.casefold() not in {k.casefold() for k in merged}:
            merged[city] = None

    result = sorted(merged.keys(), key=lambda c: c.casefold())
    # Kinshasa en tête pour la démo
    if 'Kinshasa' in result:
        result.remove('Kinshasa')
        result.insert(0, 'Kinshasa')

    cache.set(CACHE_KEY, result, CACHE_TTL)
    return result


def ville_choices(*, empty_label: str = 'Sélectionner une ville'):
    """Choix pour un champ Select Django."""
    villes = get_villes_rdc()
    return [('', empty_label)] + [(v, v) for v in villes]
