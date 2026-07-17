"""
Procédure d'indemnisation automatique à la validation d'un sinistre.
"""
from decimal import Decimal

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from documents.models import Document, DocumentType
from notifications.models import NotificationType
from notifications.services import create_notification, notify_staff, STAFF_ROLES_ALL
from core.currency import format_usd
from contrats.services import generate_retrait_bancaire_pdf

from .models import RapportIndemnisation, Sinistre, SinistreStatut, StatutRetraitPaiement


class IndemnisationError(Exception):
    pass


def _decimal(value):
    if value is None:
        return Decimal('0')
    return Decimal(str(value))


def _build_report_content(sinistre, rapport, contrat):
    client = sinistre.client
    lines = [
        'SONAS — RAPPORT D\'INDEMNISATION',
        '=' * 50,
        f'Référence rapport : {rapport.reference}',
        f'Référence sinistre : {sinistre.reference}',
        f'Contrat : {contrat.reference}',
        f'Client : {client.display_name}',
        f'Bien : {sinistre.bien.reference} — {sinistre.bien.ville}',
        f'Type de sinistre : {sinistre.get_type_sinistre_display()}',
        f'Date du sinistre : {sinistre.date_sinistre.strftime("%d/%m/%Y")}',
        f'Date de génération : {timezone.now().strftime("%d/%m/%Y %H:%M")}',
        '',
        '--- MONTANTS (USD) ---',
        f'Montant demandé : {format_usd(rapport.montant_demande)}',
        f'Plafond sinistre : {format_usd(rapport.plafond_sinistre)}',
        f'Plafond contrat disponible (avant) : {format_usd(rapport.plafond_contrat_avant)}',
        f'Montant indemnisé : {format_usd(rapport.montant_indemnise)}',
        f'Montant non couvert : {format_usd(rapport.montant_non_couvert)}',
        f'Plafond contrat disponible (après) : {format_usd(rapport.plafond_contrat_apres)}',
        '',
        '--- DÉCISION CONTRACTUELLE ---',
    ]
    if rapport.depassement_detecte:
        lines.append('Dépassement de plafond détecté : OUI')
        if rapport.contrat_invalide:
            lines.append('Le contrat est devenu INACTIF (plafond dépassé ou épuisé).')
            lines.append('Les déclarations de sinistre ne sont plus possibles sur ce contrat.')
        else:
            lines.append('Le contrat reste actif avec plafond mis à jour.')
    else:
        lines.append('Dépassement de plafond détecté : NON')
        if rapport.contrat_invalide:
            lines.append('Le plafond contractuel est épuisé : le contrat est devenu INACTIF.')
        else:
            lines.append('Le contrat reste actif.')

    lines.extend([
        '',
        '--- DESCRIPTION DU SINISTRE ---',
        sinistre.description,
        '',
        'Ce document constitue la copie officielle du rapport d\'indemnisation.',
        'SONAS — Service indemnisation',
    ])
    return '\n'.join(lines)


@transaction.atomic
def lancer_indemnisation(sinistre, montant_demande, valide_par):
    """
    Calcule l'indemnisation, déduit du contrat, invalide si dépassement,
    génère le rapport et notifie agents + client.
    """
    if sinistre.statut != SinistreStatut.VALIDE:
        raise IndemnisationError('Le sinistre doit être au statut Validé.')

    if sinistre.rapports_indemnisation.exists():
        raise IndemnisationError('Une indemnisation a déjà été traitée pour ce sinistre.')

    contrat = sinistre.contrat
    montant_demande = _decimal(montant_demande)
    if montant_demande <= 0:
        raise IndemnisationError('Le montant d\'indemnisation doit être strictement positif.')

    plafond_sinistre = _decimal(sinistre.plafond_indemnisation)
    plafond_contrat_avant = contrat.plafond_disponible

    if plafond_sinistre <= 0 and contrat.plafond_indemnisation > 0:
        plafond_sinistre = plafond_contrat_avant

    montant_indemnise = min(
        montant_demande,
        plafond_sinistre if plafond_sinistre > 0 else montant_demande,
        plafond_contrat_avant if plafond_contrat_avant > 0 else montant_demande,
    )

    if contrat.plafond_indemnisation > 0 and plafond_contrat_avant <= 0:
        montant_indemnise = Decimal('0')

    montant_non_couvert = montant_demande - montant_indemnise
    depassement = montant_non_couvert > 0

    plafond_contrat_apres = plafond_contrat_avant - montant_indemnise
    if plafond_contrat_apres < 0:
        plafond_contrat_apres = Decimal('0')

    contrat_invalide = False
    motif_inactivation = ''

    if montant_indemnise > 0:
        contrat.deduire_indemnisation(montant_indemnise)
        contrat.refresh_from_db()
        plafond_contrat_apres = contrat.plafond_disponible

    if depassement:
        motif_inactivation = f'Dépassement plafond — sinistre {sinistre.reference}'
        contrat.invalider_plafond(motif=motif_inactivation)
        contrat_invalide = True
        plafond_contrat_apres = Decimal('0')
    elif contrat.plafond_indemnisation > 0 and contrat.plafond_epuise:
        motif_inactivation = f'Plafond épuisé — sinistre {sinistre.reference}'
        contrat.invalider_plafond(motif=motif_inactivation)
        contrat_invalide = True
        plafond_contrat_apres = Decimal('0')

    sinistre.montant_indemnise = montant_indemnise
    sinistre.save(update_fields=['montant_indemnise', 'updated_at'])

    rapport = RapportIndemnisation(
        sinistre=sinistre,
        montant_demande=montant_demande,
        montant_indemnise=montant_indemnise,
        montant_non_couvert=montant_non_couvert,
        plafond_sinistre=plafond_sinistre,
        plafond_contrat_avant=plafond_contrat_avant,
        plafond_contrat_apres=plafond_contrat_apres,
        depassement_detecte=depassement,
        contrat_invalide=contrat_invalide,
        genere_par=valide_par,
        contenu='',
    )
    rapport.contenu = _build_report_content(sinistre, rapport, contrat)
    rapport.save()

    doc = Document(
        sinistre=sinistre,
        type_document=DocumentType.RAPPORT,
        titre=f'Rapport d\'indemnisation {rapport.reference}',
        uploaded_by=valide_par,
    )
    doc.fichier.save(
        f'{rapport.reference}.txt',
        ContentFile(rapport.contenu.encode('utf-8')),
    )
    doc.save()

    rapport.document = doc
    rapport.copie_client_envoyee = True
    rapport.save(update_fields=['document', 'copie_client_envoyee'])

    msg_client = (
        f'Indemnisation de {format_usd(montant_indemnise)} enregistrée pour le sinistre {sinistre.reference}. '
        f'Le rapport {rapport.reference} et le document de retrait bancaire sont disponibles.'
    )
    if depassement:
        msg_client += (
            f' Attention : {format_usd(montant_non_couvert)} n\'ont pas pu être couverts. '
            f'Le contrat {contrat.reference} est devenu inactif.'
        )
    elif contrat_invalide:
        msg_client += (
            f' Le plafond du contrat {contrat.reference} est épuisé : '
            f'le contrat est devenu inactif.'
        )

    # Document de retrait + statut ROUGE jusqu'à preuve client
    if montant_indemnise > 0:
        retrait_doc = generate_retrait_bancaire_pdf(sinistre, valide_par, montant_indemnise)
        sinistre.document_retrait_bancaire = retrait_doc
        sinistre.statut_retrait_paiement = StatutRetraitPaiement.ROUGE
        sinistre.save(update_fields=[
            'document_retrait_bancaire', 'statut_retrait_paiement', 'updated_at',
        ])

    if contrat_invalide:
        create_notification(
            user=sinistre.client.user,
            notif_type=NotificationType.STATUT_CHANGE,
            title=f'Contrat {contrat.reference} inactif',
            message=(
                f'Votre contrat {contrat.reference} est devenu inactif '
                f'suite au traitement du sinistre {sinistre.reference}. '
                f'Les nouvelles déclarations de sinistre ne sont plus possibles.'
            ),
            obj=contrat,
            priority='high',
        )
        notify_staff(
            roles=STAFF_ROLES_ALL,
            notif_type=NotificationType.STATUT_CHANGE,
            title=f'Contrat {contrat.reference} inactif',
            message=motif_inactivation or f'Plafond atteint — sinistre {sinistre.reference}',
            obj=contrat,
            priority='high',
        )

    create_notification(
        user=sinistre.client.user,
        notif_type=NotificationType.STATUT_CHANGE,
        title=f'Indemnisation — sinistre {sinistre.reference}',
        message=msg_client,
        obj=sinistre,
        priority='high' if depassement or contrat_invalide else 'normal',
    )

    notify_staff(
        roles=STAFF_ROLES_ALL,
        notif_type=NotificationType.ACTION_PENDING,
        title=f'Rapport d\'indemnisation {rapport.reference}',
        message=(
            f'Sinistre {sinistre.reference} — {format_usd(montant_indemnise)} indemnisés '
            f'({client_label(sinistre)}).'
        ),
        obj=sinistre,
        priority='high' if depassement else 'normal',
    )

    return rapport


def client_label(sinistre):
    return sinistre.client.display_name
