"""
Workflow métier : déclaration bien → police + contrat EN_ATTENTE + bon de paiement.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from biens.models import Bien
from notifications.models import ActionType
from notifications.services import create_notification, create_pending_action, notify_staff

from .models import (
    TYPE_ASSURANCE_LABELS,
    Contrat,
    ContratStatut,
    GrilleTarifaire,
    PoliceAssurance,
    default_contrat_dates,
)
from .services import generate_bon_paiement_pdf, generate_contrat_pdf


DEFAULT_PRIMES = {
    'APPARTEMENT': (Decimal('850'), Decimal('50000')),
    'MAISON': (Decimal('1200'), Decimal('75000')),
    'LOCAL_COMMERCIAL': (Decimal('1800'), Decimal('100000')),
    'IMMEUBLE': (Decimal('3500'), Decimal('250000')),
    'AUTRE': (Decimal('1000'), Decimal('50000')),
}


def ensure_default_grilles():
    """Crée une grille tarifaire de base si la table est vide."""
    if GrilleTarifaire.objects.exists():
        return
    rows = [
        ('APPARTEMENT', 'Appartement — standard', 0, 150000, 850, 50000),
        ('APPARTEMENT', 'Appartement — premium', 150000.01, None, 1400, 100000),
        ('MAISON', 'Maison — standard', 0, 300000, 1200, 75000),
        ('MAISON', 'Maison — premium', 300000.01, None, 2200, 150000),
        ('LOCAL_COMMERCIAL', 'Local commercial', 0, None, 1800, 100000),
        ('IMMEUBLE', 'Immeuble', 0, None, 3500, 250000),
        ('AUTRE', 'Multirisque — standard', 0, None, 1000, 50000),
    ]
    for type_bien, libelle, vmin, vmax, prime, plafond in rows:
        GrilleTarifaire.objects.create(
            type_bien=type_bien,
            libelle=libelle,
            valeur_min=vmin,
            valeur_max=vmax,
            prime_annuelle=prime,
            plafond_indemnisation=plafond,
        )


def resolve_pricing(bien: Bien, grille=None):
    """Retourne (grille, prime, plafond) pour un bien."""
    ensure_default_grilles()
    grille = grille or bien.grille_tarifaire or GrilleTarifaire.trouver_pour(
        bien.type_bien, bien.valeur_estimee,
    )
    if grille:
        return grille, grille.prime_annuelle, grille.plafond_indemnisation
    prime, plafond = DEFAULT_PRIMES.get(bien.type_bien, DEFAULT_PRIMES['AUTRE'])
    return None, prime, plafond


@transaction.atomic
def generer_police_et_contrat(bien, generated_by, grille=None):
    """
    Après déclaration d'un bien : crée police + contrat EN_ATTENTE + PDFs.
    Ne recrée pas si un contrat EN_ATTENTE/BROUILLON/ACTIF existe déjà.
    """
    existing = Contrat.objects.filter(
        bien=bien,
        statut__in=(ContratStatut.EN_ATTENTE, ContratStatut.BROUILLON, ContratStatut.ACTIF),
    ).first()
    if existing:
        return existing, getattr(existing, 'police_assurance', None)

    grille, prime, plafond = resolve_pricing(bien, grille=grille)
    if grille and not bien.grille_tarifaire_id:
        bien.grille_tarifaire = grille
        bien.save(update_fields=['grille_tarifaire', 'updated_at'])

    date_debut, date_fin = default_contrat_dates()
    contrat = Contrat(
        client=bien.client,
        bien=bien,
        date_debut=date_debut,
        date_fin=date_fin,
        statut=ContratStatut.EN_ATTENTE,
        montant_annuel=prime,
        plafond_indemnisation=plafond,
        grille_tarifaire=grille,
        date_souscription=timezone.now(),
    )
    contrat.save()

    type_assurance = TYPE_ASSURANCE_LABELS.get(bien.type_bien, 'Assurance multirisque')
    police = PoliceAssurance.objects.create(
        client=bien.client,
        bien=bien,
        contrat=contrat,
        type_assurance=type_assurance,
        prime_annuelle=prime,
        plafond_indemnisation=plafond,
    )

    generate_contrat_pdf(contrat, generated_by)
    generate_bon_paiement_pdf(contrat, generated_by)

    create_pending_action(
        user=bien.client.user,
        action_type='DOCUMENTS_MANQUANTS',
        title=f'Compléter le dossier {contrat.reference}',
        description='Ajoutez les justificatifs du bien et déposez la preuve de paiement.',
        obj=contrat.bien,
    )
    create_notification(
        user=bien.client.user,
        notif_type='STATUT_CHANGE',
        title=f'Contrat {contrat.reference} généré',
        message=(
            f'Police {police.reference} et bon de paiement {contrat.bon_paiement_reference} '
            f'créés. Téléchargez le bon, payez en banque puis déposez la preuve.'
        ),
        obj=contrat,
    )
    notify_staff(
        title=f'Contrat {contrat.reference} en attente',
        message=(
            f'{bien.client.display_name} — bien {bien.reference}. '
            f'Prime : ${prime} — en attente documents + paiement.'
        ),
        obj=contrat,
        pending_action_type=ActionType.CONTRAT_NON_FINALISE,
        pending_title=f'Suivre le contrat {contrat.reference}',
        pending_description='Documents + validation paiement requis avant activation.',
        exclude_user=generated_by if generated_by and not getattr(generated_by, 'is_client', False) else None,
    )
    return contrat, police
