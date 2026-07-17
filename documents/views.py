from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from clients.models import ActiviteClient
from clients.services import log_client_activity
from notifications.services import resolve_pending_for_object
from sinistres.models import Sinistre
from biens.models import Bien
from .forms import DocumentUploadForm
from .models import Document, DocumentType
from .services import (
    filter_internal_documents,
    get_document_filter_clients,
    get_internal_documents_queryset,
)


GENERATED_PDF_TYPES = {
    DocumentType.CONTRAT_PDF,
    DocumentType.BON_PAIEMENT,
    DocumentType.RETRAIT_BANCAIRE,
}


def _user_can_access_sinistre(user, sinistre):
    if user.is_internal:
        return True
    return hasattr(user, 'client_profile') and sinistre.contrat.client_id == user.client_profile.id


def _user_can_access_bien(user, bien):
    if user.is_internal:
        return True
    return hasattr(user, 'client_profile') and bien.client_id == user.client_profile.id


def _user_can_access_document(user, document):
    if user.is_internal:
        return True
    if not hasattr(user, 'client_profile'):
        return False
    client = document.client
    return client is not None and client.pk == user.client_profile.pk


def _documents_list_url(user):
    return 'documents_client:list' if user.is_client else 'documents:list'


def _document_ns(user):
    return 'documents_client' if user.is_client else 'documents'


def _back_url_for_document(request, document):
    if document.contrat_id:
        if request.user.is_client:
            return reverse('contrats_client:detail', args=[document.contrat_id])
        return reverse('contrats:detail', args=[document.contrat_id])
    if document.sinistre_id:
        if request.user.is_client:
            return reverse('sinistres_client:detail', args=[document.sinistre_id])
        return reverse('sinistres:detail', args=[document.sinistre_id])
    if document.bien_id:
        if request.user.is_client:
            return reverse('biens_client:detail', args=[document.bien_id])
        return reverse('biens:detail', args=[document.bien_id])
    ns = _document_ns(request.user)
    return reverse(f'{ns}:list')


def _retrait_montant(sinistre):
    montant = getattr(sinistre, 'montant_indemnise', None)
    if montant is not None:
        return montant
    rapport = getattr(sinistre, 'rapport', None) or getattr(sinistre, 'rapport_indemnisation', None)
    if rapport is not None:
        return getattr(rapport, 'montant_indemnise', None) or getattr(rapport, 'montant', 0) or 0
    return getattr(sinistre, 'montant_estime', None) or 0


def _render_generated_html(document, *, pdf_mode, download_url='', back_url='', theme_preference='system'):
    from contrats.services import (
        render_bon_paiement_html,
        render_contrat_html,
        render_retrait_html,
    )

    extra = {'theme_preference': theme_preference}

    if document.type_document == DocumentType.CONTRAT_PDF and document.contrat_id:
        return render_contrat_html(
            document.contrat,
            pdf_mode=pdf_mode,
            download_url=download_url,
            back_url=back_url,
            **extra,
        )
    if document.type_document == DocumentType.BON_PAIEMENT and document.contrat_id:
        return render_bon_paiement_html(
            document.contrat,
            pdf_mode=pdf_mode,
            download_url=download_url,
            back_url=back_url,
            **extra,
        )
    if document.type_document == DocumentType.RETRAIT_BANCAIRE and document.sinistre_id:
        return render_retrait_html(
            document.sinistre,
            _retrait_montant(document.sinistre),
            pdf_mode=pdf_mode,
            download_url=download_url,
            back_url=back_url,
            **extra,
        )
    return None


@login_required
def document_preview(request, pk):
    """Aperçu HTML (documents générés) ou iframe fichier + lien de téléchargement."""
    document = get_object_or_404(
        Document.objects.select_related(
            'contrat', 'contrat__client', 'contrat__client__user', 'contrat__bien',
            'sinistre', 'sinistre__contrat', 'sinistre__contrat__client',
            'sinistre__contrat__client__user', 'sinistre__contrat__bien',
            'bien', 'bien__client',
        ),
        pk=pk,
    )
    if not _user_can_access_document(request.user, document):
        messages.error(request, 'Accès refusé.')
        return redirect(_documents_list_url(request.user))

    ns = _document_ns(request.user)
    download_url = reverse(f'{ns}:download', args=[document.pk])
    back_url = _back_url_for_document(request, document)

    if document.type_document in GENERATED_PDF_TYPES:
        theme = getattr(request.user, 'theme_preference', None) or 'system'
        html = _render_generated_html(
            document,
            pdf_mode=False,
            download_url=download_url,
            back_url=back_url,
            theme_preference=theme,
        )
        if html:
            return HttpResponse(html)

    name = (document.fichier.name or '').lower()
    return render(request, 'documents/file_preview.html', {
        'document': document,
        'download_url': download_url,
        'back_url': back_url,
        'is_pdf': name.endswith('.pdf'),
        'is_image': name.endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif')),
    })


@login_required
def document_download(request, pk):
    """Téléchargement du PDF (régénère via Playwright si besoin)."""
    document = get_object_or_404(
        Document.objects.select_related(
            'contrat', 'contrat__client', 'contrat__client__user', 'contrat__bien',
            'sinistre', 'sinistre__contrat', 'sinistre__contrat__client',
            'sinistre__contrat__client__user', 'sinistre__contrat__bien',
        ),
        pk=pk,
    )
    if not _user_can_access_document(request.user, document):
        messages.error(request, 'Accès refusé.')
        return redirect(_documents_list_url(request.user))

    safe_title = ''.join(c if c.isalnum() or c in '-_' else '_' for c in document.titre)[:80]
    filename = f'{safe_title or "document"}.pdf'

    # Documents générés : toujours régénérés via Playwright pour coller à l'aperçu HTML
    if document.type_document in GENERATED_PDF_TYPES:
        from core.pdf import html_to_pdf

        html = _render_generated_html(document, pdf_mode=True)
        if html:
            pdf_bytes = html_to_pdf(html)
            if pdf_bytes:
                response = HttpResponse(pdf_bytes, content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response

    name = (document.fichier.name or '').lower()
    if name.endswith('.pdf') and document.fichier:
        try:
            return FileResponse(
                document.fichier.open('rb'),
                as_attachment=True,
                filename=filename,
                content_type='application/pdf',
            )
        except Exception:
            pass

    if document.fichier:
        try:
            return FileResponse(
                document.fichier.open('rb'),
                as_attachment=True,
                filename=document.fichier.name.split('/')[-1],
            )
        except Exception as exc:
            raise Http404('Fichier introuvable.') from exc

    raise Http404('Document introuvable.')


@login_required
def document_upload(request):
    sinistre_id = request.GET.get('sinistre') or request.POST.get('sinistre_id')
    bien_id = request.GET.get('bien') or request.POST.get('bien_id')
    sinistre = Sinistre.objects.filter(pk=sinistre_id).select_related('contrat').first() if sinistre_id else None
    bien = Bien.objects.filter(pk=bien_id).first() if bien_id else None

    if sinistre and not _user_can_access_sinistre(request.user, sinistre):
        messages.error(request, 'Accès refusé.')
        return redirect(_documents_list_url(request.user))

    if bien and not _user_can_access_bien(request.user, bien):
        messages.error(request, 'Accès refusé.')
        return redirect(_documents_list_url(request.user))

    if sinistre and bien:
        messages.error(request, 'Associez le document à un seul élément.')
        bien = None

    link_mode = 'both'
    if sinistre:
        link_mode = 'sinistre'
    elif bien:
        link_mode = 'bien'

    if request.method == 'POST':
        form = DocumentUploadForm(
            request.POST, request.FILES,
            user=request.user,
            link_mode=link_mode,
        )
        if form.is_valid():
            doc = form.save(commit=False)
            doc.uploaded_by = request.user
            if sinistre:
                doc.sinistre = sinistre
            if bien:
                doc.bien = bien
            doc.save()

            if doc.sinistre_id:
                resolve_pending_for_object(doc.sinistre, action_type='SINISTRE_INCOMPLET')
                if request.user.is_client:
                    log_client_activity(
                        request.user.client_profile,
                        ActiviteClient.TypeActivite.DOCUMENT_UPLOAD,
                        f'Document ajouté au sinistre {doc.sinistre.reference}',
                        request.user,
                    )
                messages.success(request, 'Document associé au sinistre.')
                if request.user.is_client:
                    return redirect('sinistres_client:detail', pk=doc.sinistre_id)
                return redirect('sinistres:detail', pk=doc.sinistre_id)

            if doc.bien_id:
                resolve_pending_for_object(doc.bien, action_type='BIEN_INCOMPLET')
                resolve_pending_for_object(doc.bien, action_type='DOCUMENTS_MANQUANTS')
                if request.user.is_client:
                    log_client_activity(
                        request.user.client_profile,
                        ActiviteClient.TypeActivite.DOCUMENT_UPLOAD,
                        f'Document ajouté au bien {doc.bien.reference}',
                        request.user,
                    )
                messages.success(request, 'Document associé au bien.')
                if request.user.is_client:
                    return redirect('biens_client:detail', pk=doc.bien_id)
                return redirect('biens:detail', pk=doc.bien_id)

            messages.error(request, 'Association impossible.')
    else:
        initial = {}
        if sinistre:
            initial['sinistre'] = sinistre
        if bien:
            initial['bien'] = bien
        form = DocumentUploadForm(
            initial=initial,
            user=request.user,
            link_mode=link_mode,
        )

    if link_mode == 'bien':
        guide_steps = [
            'Sélectionner le type de document',
            'Joindre le fichier',
            'Validation par un agent',
        ]
        guide_tip = 'Formats acceptés : PDF, images (JPG, PNG). Titre de propriété, bail, diagnostics…'
    elif link_mode == 'sinistre':
        guide_steps = [
            'Sélectionner le type de pièce',
            'Joindre photos ou devis',
            'Instruction du dossier',
        ]
        guide_tip = 'Formats acceptés : PDF, images (JPG, PNG). Photos, devis, constats amiables…'
    else:
        guide_steps = [
            'Choisir bien ou sinistre',
            'Sélectionner le type',
            'Envoyer le fichier',
        ]
        guide_tip = 'Formats acceptés : PDF, images (JPG, PNG). Taille maximale selon la configuration du serveur.'

    return render(request, 'documents/upload.html', {
        'form': form,
        'sinistre': sinistre,
        'bien': bien,
        'link_mode': link_mode,
        'guide_steps': guide_steps,
        'guide_tip': guide_tip,
    })


@login_required
def document_list(request):
    if request.user.is_client:
        client = request.user.client_profile
        docs = Document.objects.filter(
            models.Q(sinistre__contrat__client=client)
            | models.Q(bien__client=client)
            | models.Q(contrat__client=client)
        ).select_related('sinistre', 'sinistre__contrat', 'bien', 'contrat')
        context = {'documents': docs, 'is_internal_list': False}
    else:
        client_id = request.GET.get('client', '').strip()
        type_document = request.GET.get('type', '').strip()
        search = request.GET.get('q', '').strip()

        docs = get_internal_documents_queryset()
        docs = filter_internal_documents(
            docs,
            client_id=client_id or None,
            type_document=type_document or None,
            search=search,
        )

        context = {
            'documents': docs,
            'is_internal_list': True,
            'filter_clients': get_document_filter_clients(),
            'document_types': DocumentType.choices,
            'active_client': client_id,
            'active_type': type_document,
            'search': search,
            'results_count': docs.count(),
        }

    return render(request, 'documents/list.html', context)
