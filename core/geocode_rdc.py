"""
Géocodage d'adresses en RDC via OpenStreetMap Nominatim.

Recherche limitée à countrycodes=cd et à la ville sélectionnée,
pour des suggestions / validations crédibles sur la carte.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache

from django.core.cache import cache

logger = logging.getLogger(__name__)

NOMINATIM_SEARCH = 'https://nominatim.openstreetmap.org/search'
USER_AGENT = 'SONAS-Demo/1.0 (TFC Francesco; educational geocoding; contact@sonas.local)'
COUNTRY_CODE = 'cd'
CACHE_TTL = 60 * 60 * 12
MIN_QUERY_LEN = 3
_last_request_at = 0.0


def _cache_key(prefix: str, *parts: str) -> str:
    raw = '|'.join(_normalize(p).casefold() for p in parts)
    digest = hashlib.sha1(raw.encode('utf-8')).hexdigest()[:24]
    return f'{prefix}_{digest}'


def _rate_limit(min_interval: float = 1.05) -> None:
    global _last_request_at
    now = time.monotonic()
    wait = min_interval - (now - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def _http_get_json(url: str, timeout: int = 20) -> list | dict | None:
    _rate_limit()
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': USER_AGENT,
            'Accept': 'application/json',
            'Accept-Language': 'fr',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning('Nominatim indisponible: %s', exc)
        return None


def _normalize(text: str) -> str:
    return ' '.join((text or '').strip().split())


def _city_key(ville: str) -> str:
    return _normalize(ville).casefold()


def _result_in_city(item: dict, ville: str) -> bool:
    """Vérifie que le résultat Nominatim concerne bien la ville RDC demandée."""
    if not ville:
        return False
    key = _city_key(ville)
    addr = item.get('address') or {}
    candidates = [
        addr.get('city'),
        addr.get('town'),
        addr.get('municipality'),
        addr.get('village'),
        addr.get('county'),
        addr.get('state'),
        item.get('display_name'),
    ]
    for raw in candidates:
        if raw and key in _normalize(str(raw)).casefold():
            return True
    return False


def _is_rdc(item: dict) -> bool:
    addr = item.get('address') or {}
    cc = (addr.get('country_code') or '').lower()
    if cc == COUNTRY_CODE:
        return True
    display = (item.get('display_name') or '').casefold()
    return 'congo' in display and ('démocratique' in display or 'democratique' in display or 'kinshasa' in display)


def _serialize(item: dict) -> dict:
    lat = item.get('lat')
    lon = item.get('lon')
    display = item.get('display_name') or ''
    # Adresse courte utilisable dans le formulaire (avant le pays)
    parts = [p.strip() for p in display.split(',') if p.strip()]
    short = ', '.join(parts[:3]) if parts else display
    maps_url = ''
    if lat and lon:
        maps_url = f'https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=17/{lat}/{lon}'
    return {
        'label': display,
        'adresse': short,
        'lat': lat,
        'lon': lon,
        'maps_url': maps_url,
        'postcode': (item.get('address') or {}).get('postcode') or '',
    }


@lru_cache(maxsize=128)
def _city_bbox_cached(ville: str) -> tuple[str, ...] | None:
    """Bounding box Nominatim de la ville (viewbox: left,top,right,bottom)."""
    ville = _normalize(ville)
    if not ville:
        return None
    cache_key = _cache_key('sonas_bbox_rdc', ville)
    cached = cache.get(cache_key)
    if cached is not None:
        return tuple(cached) if cached else None

    params = {
        'city': ville,
        'country': 'Democratic Republic of the Congo',
        'countrycodes': COUNTRY_CODE,
        'format': 'json',
        'limit': 1,
        'addressdetails': 1,
    }
    url = f'{NOMINATIM_SEARCH}?{urllib.parse.urlencode(params)}'
    data = _http_get_json(url)
    bbox = None
    if isinstance(data, list) and data:
        item = data[0]
        if _is_rdc(item) and item.get('boundingbox'):
            # Nominatim: [south, north, west, east] → viewbox left,top,right,bottom
            south, north, west, east = item['boundingbox']
            bbox = (west, north, east, south)
    cache.set(cache_key, list(bbox) if bbox else [], CACHE_TTL)
    return tuple(bbox) if bbox else None


def search_adresses_rdc(ville: str, query: str, *, limit: int = 6) -> tuple[list[dict], bool]:
    """
    Suggestions d'adresses OSM pour une ville RDC.
    Retourne (résultats, api_ok). api_ok=False si Nominatim est injoignable.
    """
    ville = _normalize(ville)
    query = _normalize(query)
    if not ville or len(query) < MIN_QUERY_LEN:
        return [], True

    cache_key = _cache_key('sonas_geo_search', ville, query, str(limit))
    cached = cache.get(cache_key)
    if cached is not None:
        return cached, True

    params = {
        'q': f'{query}, {ville}, Democratic Republic of the Congo',
        'countrycodes': COUNTRY_CODE,
        'format': 'json',
        'addressdetails': 1,
        'limit': max(limit * 2, 8),
    }
    bbox = _city_bbox_cached(ville)
    if bbox:
        params['viewbox'] = ','.join(bbox)
        params['bounded'] = 1

    url = f'{NOMINATIM_SEARCH}?{urllib.parse.urlencode(params)}'
    data = _http_get_json(url)
    if data is None:
        return [], False

    results: list[dict] = []
    if isinstance(data, list):
        for item in data:
            if not _is_rdc(item):
                continue
            if not _result_in_city(item, ville):
                continue
            results.append(_serialize(item))
            if len(results) >= limit:
                break

    # Relâchement : si viewbox trop strict, retenter sans bounded
    if not results and bbox:
        params.pop('bounded', None)
        url = f'{NOMINATIM_SEARCH}?{urllib.parse.urlencode(params)}'
        data = _http_get_json(url)
        if data is None:
            return [], False
        if isinstance(data, list):
            for item in data:
                if _is_rdc(item) and _result_in_city(item, ville):
                    results.append(_serialize(item))
                    if len(results) >= limit:
                        break

    cache.set(cache_key, results, CACHE_TTL)
    return results, True


def verify_adresse_rdc(adresse: str, ville: str) -> tuple[bool, dict | None, str]:
    """
    Vérifie qu'une adresse est localisable sur la carte en RDC dans la ville donnée.
    Retourne (ok, détail, message_erreur).
    Si Nominatim est hors-ligne : ok=True (ne bloque pas la démo).
    """
    adresse = _normalize(adresse)
    ville = _normalize(ville)
    if not adresse or not ville:
        return False, None, 'Ville et adresse sont obligatoires pour la vérification carte.'

    cache_key = _cache_key('sonas_geo_verify', ville, adresse)
    cached = cache.get(cache_key)
    if cached is not None:
        return bool(cached.get('ok')), cached.get('result'), cached.get('error', '')

    matches, api_ok = search_adresses_rdc(ville, adresse, limit=5)
    if not api_ok:
        logger.warning('Vérification adresse assouplie (Nominatim indisponible): %s / %s', adresse, ville)
        return True, None, ''

    best = None
    addr_key = adresse.casefold()
    for item in matches:
        label = (item.get('label') or '').casefold()
        short = (item.get('adresse') or '').casefold()
        if addr_key in label or addr_key in short or short in addr_key or any(
            part and part in label for part in addr_key.replace(',', ' ').split() if len(part) > 3
        ):
            best = item
            break
    if not best and matches:
        best = matches[0]

    if best is None:
        error = (
            f'Adresse introuvable sur la carte OpenStreetMap pour « {ville} » (RDC). '
            'Choisissez une suggestion ou une rue réelle de cette ville.'
        )
        cache.set(cache_key, {'ok': False, 'result': None, 'error': error}, CACHE_TTL)
        return False, None, error

    cache.set(cache_key, {'ok': True, 'result': best, 'error': ''}, CACHE_TTL)
    return True, best, ''
