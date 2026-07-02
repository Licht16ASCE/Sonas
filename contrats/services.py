"""
Génération du contrat d'assurance au format PDF à partir du modèle visuel web.
"""
import io
import logging
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils import timezone

from documents.models import Document, DocumentType

logger = logging.getLogger(__name__)

INLINE_FIELD_CLASS = 'contrat-inline-field'


def get_biens_metadata(client, queryset=None):
    """Métadonnées biens pour préremplissage dynamique du contrat visuel."""
    from biens.models import Bien, BienStatut
    from contrats.models import Contrat, ContratStatut

    if queryset is None:
        biens_pris = Contrat.objects.filter(
            client=client,
            statut__in=(ContratStatut.BROUILLON, ContratStatut.ACTIF),
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


def build_contrat_context(contrat, client, form=None):
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
        'assureur': 'SONAS Assurances',
    }


def generate_contrat_pdf(contrat, generated_by):
    """
    Génère le PDF contractuel signé et l'enregistre comme document CONTRAT_PDF.
    Retourne le Document créé ou None si la génération PDF échoue (fallback texte).
    """
    context = build_contrat_context(contrat, contrat.client)
    html = render_to_string('contrats/contrat_pdf.html', context)

    pdf_bytes = _html_to_pdf(html)
    ext = '.pdf' if pdf_bytes else '.html'
    content = pdf_bytes if pdf_bytes else html.encode('utf-8')
    mime_label = 'PDF' if pdf_bytes else 'HTML'

    titre = f'Contrat d\'assurance {contrat.reference}'
    doc = Document(
        contrat=contrat,
        bien=contrat.bien,
        type_document=DocumentType.CONTRAT_PDF,
        titre=titre,
        uploaded_by=generated_by,
    )
    filename = f'{contrat.reference}{ext}'
    doc.fichier.save(filename, ContentFile(content), save=True)

    logger.info('Contrat %s enregistré en %s', contrat.reference, mime_label)
    return doc


def _html_to_pdf(html):
    try:
        from xhtml2pdf import pisa
    except ImportError:
        logger.warning('xhtml2pdf non installé — fallback HTML')
        return None

    buffer = io.BytesIO()
    result = pisa.CreatePDF(src=html, dest=buffer, encoding='utf-8')
    if result.err:
        logger.error('Erreur génération PDF contrat: %s', result.err)
        return None
    return buffer.getvalue()
