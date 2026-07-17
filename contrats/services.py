"""
Génération des documents PDF (contrat, bon de paiement, retrait)
via HTML → Playwright (même stack que WeddingPlanner).
"""
import logging
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils import timezone

from core.pdf import html_to_pdf
from documents.models import Document, DocumentType

logger = logging.getLogger(__name__)

INLINE_FIELD_CLASS = 'contrat-inline-field'
ASSUREUR = 'SONAS Assurances'


def _load_document_css() -> str:
    css_path = Path(settings.BASE_DIR) / 'static' / 'css' / 'sonas_pdf.css'
    try:
        return css_path.read_text(encoding='utf-8')
    except OSError:
        return ''


def get_biens_metadata(client, queryset=None):
    """Métadonnées biens pour préremplissage dynamique du contrat visuel."""
    from biens.models import Bien, BienStatut
    from contrats.models import Contrat, ContratStatut

    if queryset is None:
        biens_pris = Contrat.objects.filter(
            client=client,
            statut__in=(
                ContratStatut.EN_ATTENTE,
                ContratStatut.BROUILLON,
                ContratStatut.ACTIF,
            ),
        ).values_list('bien_id', flat=True)
        queryset = Bien.objects.filter(
            client=client, statut=BienStatut.VALIDE,
        ).exclude(pk__in=biens_pris)

    return {
        str(b.pk): {
            'reference': b.reference,
            'type': b.get_type_bien_display(),
            'type_code': b.type_bien,
            'adresse': b.adresse,
            'code_postal': b.code_postal,
            'ville': b.ville,
            'surface': str(b.surface_m2) if b.surface_m2 else '',
        }
        for b in queryset
    }


def build_contrat_context(contrat, client, form=None, *, pdf_mode=True,
                          download_url='', back_url='', theme_preference='system'):
    """Contexte partagé web + PDF pour le corps contractuel."""
    bien = contrat.bien if contrat.pk else None
    if form and not bien:
        bien = form.cleaned_data.get('bien') if hasattr(form, 'cleaned_data') else None

    return {
        'contrat': contrat,
        'client': client,
        'bien': bien,
        'form': form,
        'readonly': form is None or not form.is_bound,
        'signature_date': contrat.date_souscription or timezone.now(),
        'assureur': ASSUREUR,
        'currency': 'USD',
        'currency_symbol': '$',
        'pdf_mode': pdf_mode,
        'document_css': _load_document_css(),
        'download_url': download_url,
        'back_url': back_url,
        'theme_preference': theme_preference,
        'preview_title': f'Contrat {contrat.reference}',
        'preview_subtitle': 'Contrat d\'assurance SONAS',
    }


def build_bon_paiement_context(contrat, *, pdf_mode=True, download_url='', back_url='',
                               theme_preference='system'):
    return {
        'contrat': contrat,
        'client': contrat.client,
        'bien': contrat.bien,
        'police': getattr(contrat, 'police_assurance', None),
        'assureur': ASSUREUR,
        'generated_at': timezone.now(),
        'currency_symbol': '$',
        'pdf_mode': pdf_mode,
        'document_css': _load_document_css(),
        'download_url': download_url,
        'back_url': back_url,
        'theme_preference': theme_preference,
        'preview_title': f'Bon de paiement {contrat.bon_paiement_reference}',
        'preview_subtitle': 'Document officiel à présenter en banque',
    }


def build_retrait_context(sinistre, montant, *, pdf_mode=True, download_url='', back_url='',
                          theme_preference='system'):
    reference = f'RET-{sinistre.reference}'
    return {
        'sinistre': sinistre,
        'client': sinistre.client,
        'contrat': sinistre.contrat,
        'montant': montant,
        'assureur': ASSUREUR,
        'generated_at': timezone.now(),
        'currency_symbol': '$',
        'reference': reference,
        'pdf_mode': pdf_mode,
        'document_css': _load_document_css(),
        'download_url': download_url,
        'back_url': back_url,
        'theme_preference': theme_preference,
        'preview_title': f'Retrait bancaire {reference}',
        'preview_subtitle': 'Autorisation de retrait — indemnisation',
    }


def render_contrat_html(contrat, *, pdf_mode=True, download_url='', back_url='',
                        theme_preference='system'):
    context = build_contrat_context(
        contrat, contrat.client,
        pdf_mode=pdf_mode,
        download_url=download_url,
        back_url=back_url,
        theme_preference=theme_preference,
    )
    return render_to_string('contrats/contrat_pdf.html', context)


def render_bon_paiement_html(contrat, *, pdf_mode=True, download_url='', back_url='',
                             theme_preference='system'):
    context = build_bon_paiement_context(
        contrat,
        pdf_mode=pdf_mode,
        download_url=download_url,
        back_url=back_url,
        theme_preference=theme_preference,
    )
    return render_to_string('contrats/bon_paiement_pdf.html', context)


def render_retrait_html(sinistre, montant, *, pdf_mode=True, download_url='', back_url='',
                        theme_preference='system'):
    context = build_retrait_context(
        sinistre, montant,
        pdf_mode=pdf_mode,
        download_url=download_url,
        back_url=back_url,
        theme_preference=theme_preference,
    )
    return render_to_string('sinistres/retrait_bancaire_pdf.html', context)


def _save_pdf_document(*, html, titre, filename_stem, type_document, uploaded_by,
                       contrat=None, bien=None, sinistre=None):
    pdf_bytes = html_to_pdf(html)
    if not pdf_bytes:
        logger.error('Échec génération PDF Playwright pour %s — stockage HTML de secours', titre)
    ext = '.pdf' if pdf_bytes else '.html'
    content = pdf_bytes if pdf_bytes else html.encode('utf-8')

    doc = Document(
        contrat=contrat,
        bien=None,
        sinistre=sinistre if not contrat else None,
        type_document=type_document,
        titre=titre,
        uploaded_by=uploaded_by,
    )
    # Un seul lien : contrat OU sinistre
    if contrat:
        doc.contrat = contrat
        doc.sinistre = None
        doc.bien = None
    elif sinistre:
        doc.sinistre = sinistre
        doc.contrat = None
        doc.bien = None
    doc.fichier.save(f'{filename_stem}{ext}', ContentFile(content), save=True)
    logger.info('%s enregistré (%s)', titre, 'PDF' if pdf_bytes else 'HTML')
    return doc


def generate_contrat_pdf(contrat, generated_by):
    """Génère le PDF contractuel et l'enregistre comme Document CONTRAT_PDF."""
    html = render_contrat_html(contrat, pdf_mode=True)
    return _save_pdf_document(
        html=html,
        titre=f'Contrat d\'assurance {contrat.reference}',
        filename_stem=contrat.reference,
        type_document=DocumentType.CONTRAT_PDF,
        uploaded_by=generated_by,
        contrat=contrat,
    )


def generate_bon_paiement_pdf(contrat, generated_by):
    """Bon de paiement bancaire officiel (HTML → PDF Playwright)."""
    html = render_bon_paiement_html(contrat, pdf_mode=True)
    return _save_pdf_document(
        html=html,
        titre=f'Bon de paiement {contrat.bon_paiement_reference}',
        filename_stem=contrat.bon_paiement_reference or contrat.reference,
        type_document=DocumentType.BON_PAIEMENT,
        uploaded_by=generated_by,
        contrat=contrat,
    )


def generate_retrait_bancaire_pdf(sinistre, generated_by, montant):
    """Document officiel de retrait bancaire après indemnisation."""
    html = render_retrait_html(sinistre, montant, pdf_mode=True)
    return _save_pdf_document(
        html=html,
        titre=f'Retrait bancaire {sinistre.reference}',
        filename_stem=f'RET-{sinistre.reference}',
        type_document=DocumentType.RETRAIT_BANCAIRE,
        uploaded_by=generated_by,
        sinistre=sinistre,
    )
