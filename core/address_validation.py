"""Helpers formulaires liés à la géolocalisation RDC."""
from django.core.exceptions import ValidationError

from core.geocode_rdc import verify_adresse_rdc


def validate_adresse_ville_rdc(adresse, ville, *, required=True):
    """
    Valide adresse + ville via OpenStreetMap (RDC).
    Retourne le détail géocodé (ou None) ; lève ValidationError si invalide.
    """
    adresse = (adresse or '').strip()
    ville = (ville or '').strip()
    if not adresse:
        if required:
            raise ValidationError('Adresse obligatoire.')
        return None
    if not ville:
        raise ValidationError('Sélectionnez d\'abord une ville de la RDC.')

    ok, detail, error = verify_adresse_rdc(adresse, ville)
    if not ok:
        raise ValidationError(error or 'Adresse non vérifiable sur la carte pour cette ville.')
    return detail
