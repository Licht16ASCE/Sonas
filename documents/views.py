from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from django.shortcuts import redirect, render
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


def _user_can_access_sinistre(user, sinistre):
    if user.is_internal:
        return True
    return hasattr(user, 'client_profile') and sinistre.contrat.client_id == user.client_profile.id


def _user_can_access_bien(user, bien):
    if user.is_internal:
        return True
    return hasattr(user, 'client_profile') and bien.client_id == user.client_profile.id


def _documents_list_url(user):
    return 'documents_client:list' if user.is_client else 'documents:list'


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
