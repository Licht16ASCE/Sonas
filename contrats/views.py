from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from datetime import date, timedelta

from django.core.files.base import ContentFile

from core.decorators import client_required, internal_required
from core.filters import FILTER_CHOICES, get_active_filter
from clients.models import ActiviteClient
from clients.services import log_client_activity
from documents.models import Document, DocumentType
from notifications.models import ActionType
from notifications.services import (
    create_notification,
    create_pending_action,
    notify_staff,
    resolve_pending_for_object,
)
from .forms import ClientContratForm, ContratForm, PreuvePaiementForm
from .models import Contrat, ContratStatut, PreuvePaiement
from .services import generate_bon_paiement_pdf, generate_contrat_pdf, get_biens_metadata


@client_required
def contrat_list_client(request):
    client = request.user.client_profile
    contrats = Contrat.objects.filter(client=client).select_related('bien')
    return render(request, 'contrats/list_client.html', {'contrats': contrats})


@client_required
def contrat_detail_client(request, pk):
    client = request.user.client_profile
    contrat = get_object_or_404(
        Contrat.objects.select_related('bien', 'grille_tarifaire', 'police_assurance'),
        pk=pk, client=client,
    )
    sinistres = contrat.sinistres.all()[:5]
    preuves = contrat.preuves_paiement.all()[:5]
    return render(request, 'contrats/detail.html', {
        'contrat': contrat,
        'sinistres': sinistres,
        'show_next_steps': True,
        'document_contrat': contrat.document_contractuel,
        'document_bon_paiement': contrat.document_bon_paiement,
        'preuves': preuves,
        'preuve_form': PreuvePaiementForm(),
        'police': getattr(contrat, 'police_assurance', None),
    })


@client_required
def contrat_upload_preuve(request, pk):
    client = request.user.client_profile
    contrat = get_object_or_404(Contrat, pk=pk, client=client)
    if request.method != 'POST':
        return redirect('contrats_client:detail', pk=pk)

    form = PreuvePaiementForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, 'Fichier de preuve invalide.')
        return redirect('contrats_client:detail', pk=pk)

    fichier = form.cleaned_data['fichier']
    content = fichier.read()
    name = fichier.name

    preuve = PreuvePaiement(
        client=client,
        contrat=contrat,
        uploaded_by=request.user,
    )
    preuve.fichier.save(name, ContentFile(content), save=True)

    doc = Document(
        contrat=contrat,
        type_document=DocumentType.PREUVE_PAIEMENT,
        titre=f'Preuve de paiement {preuve.reference}',
        uploaded_by=request.user,
    )
    doc.fichier.save(name, ContentFile(content), save=True)
    preuve.document = doc
    preuve.save(update_fields=['document'])

    notify_staff(
        title=f'Preuve de paiement — {contrat.reference}',
        message=f'{client.display_name} a déposé une preuve ({preuve.reference}).',
        obj=contrat,
        pending_action_type=ActionType.CONTRAT_NON_FINALISE,
        pending_title=f'Valider le paiement {contrat.reference}',
        pending_description=f'Preuve {preuve.reference} à contrôler',
    )
    messages.success(request, 'Preuve de paiement déposée. Un agent la validera.')
    return redirect('contrats_client:detail', pk=pk)


@client_required
def contrat_create_client(request):
    client = request.user.client_profile
    contrat_preview = Contrat(client=client)

    if request.method == 'POST':
        form = ClientContratForm(request.POST, client=client)
        if form.is_valid():
            contrat = form.save(commit=False)
            contrat.client = client
            contrat.statut = ContratStatut.EN_ATTENTE
            contrat.date_souscription = timezone.now()
            contrat.save()

            generate_contrat_pdf(contrat, request.user)
            generate_bon_paiement_pdf(contrat, request.user)

            log_client_activity(
                client, ActiviteClient.TypeActivite.CONTRAT_CREE,
                f'Souscription contrat {contrat.reference}',
                request.user,
            )
            create_notification(
                user=request.user,
                notif_type='STATUT_CHANGE',
                title=f'Contrat {contrat.reference} enregistré',
                message='Contrat et bon de paiement générés. Déposez votre preuve de paiement.',
                obj=contrat,
            )
            create_pending_action(
                user=request.user,
                action_type='DOCUMENTS_MANQUANTS',
                title=f'Consolider le dossier {contrat.reference}',
                description='Ajoutez les justificatifs et la preuve de paiement.',
                obj=contrat.bien,
            )
            notify_staff(
                title=f'Contrat {contrat.reference} à activer',
                message=f'{client.display_name} a souscrit pour {contrat.bien.reference}.',
                obj=contrat,
                pending_action_type=ActionType.CONTRAT_NON_FINALISE,
                pending_title=f'Activer le contrat {contrat.reference}',
                pending_description=f'Client : {client.display_name}',
            )
            messages.success(request, 'Contrat enregistré. Téléchargez le bon de paiement.')
            return redirect('contrats_client:detail', pk=contrat.pk)
    else:
        form = ClientContratForm(client=client)

    biens_qs = form.fields['bien'].queryset
    biens_eligibles = biens_qs.count()
    biens_en_attente = client.biens.filter(statut='EN_ATTENTE').count()
    return render(request, 'contrats/form_client.html', {
        'form': form,
        'title': 'Contrat d\'assurance — souscription',
        'contrat_preview': contrat_preview,
        'client': client,
        'now': timezone.now(),
        'biens_eligibles': biens_eligibles,
        'biens_en_attente': biens_en_attente,
        'biens_meta': get_biens_metadata(client, biens_qs),
        'guide_steps': [
            'Lire et compléter le contrat',
            'Génération PDF + bon de paiement',
            'Déposer preuve de paiement',
            'Activation par un agent',
        ],
        'guide_tip': (
            f'{biens_eligibles} bien{"s" if biens_eligibles > 1 else ""} '
            f'éligible{"s" if biens_eligibles > 1 else ""}. Montants en USD ($).'
        ),
    })


@client_required
def contrat_consolidation_client(request, pk):
    client = request.user.client_profile
    contrat = get_object_or_404(
        Contrat.objects.select_related('bien'),
        pk=pk, client=client,
    )
    documents_bien = contrat.bien.documents.exclude(
        type_document__in=('CONTRAT_PDF', 'BON_PAIEMENT', 'PREUVE_PAIEMENT', 'RETRAIT_BANCAIRE'),
    ).order_by('-created_at')[:10]
    return render(request, 'contrats/consolidation.html', {
        'contrat': contrat,
        'document_contrat': contrat.document_contractuel,
        'document_bon_paiement': contrat.document_bon_paiement,
        'documents_bien': documents_bien,
        'preuve_form': PreuvePaiementForm(),
        'guide_steps': [
            'Contrat généré',
            'Bon de paiement',
            'Documents + preuve',
            'Activation agent',
        ],
        'guide_tip': 'Ajoutez titre de propriété / bail et la preuve de paiement bancaire.',
    })


@internal_required
def contrat_list(request):
    filter_key = get_active_filter(request)
    qs = Contrat.objects.select_related('client', 'client__user', 'bien')

    if filter_key == 'en_attente':
        qs = qs.filter(statut__in=(ContratStatut.EN_ATTENTE, ContratStatut.BROUILLON))
    elif filter_key == 'valides':
        qs = qs.filter(statut=ContratStatut.ACTIF)
    elif filter_key == 'rejetes':
        qs = qs.filter(statut=ContratStatut.RESILIE)
    elif filter_key == 'urgents':
        qs = qs.filter(
            statut=ContratStatut.ACTIF,
            date_fin__lte=date.today() + timedelta(days=7),
        )

    return render(request, 'contrats/list_internal.html', {
        'contrats': qs,
        'filter_choices': FILTER_CHOICES,
        'active_filter': filter_key,
    })


@internal_required
def contrat_detail(request, pk):
    contrat = get_object_or_404(
        Contrat.objects.select_related(
            'client', 'client__user', 'bien', 'grille_tarifaire', 'police_assurance',
        ),
        pk=pk,
    )
    sinistres = contrat.sinistres.all()
    preuves = contrat.preuves_paiement.select_related('uploaded_by', 'document').all()
    return render(request, 'contrats/detail_internal.html', {
        'contrat': contrat,
        'sinistres': sinistres,
        'document_contrat': contrat.document_contractuel,
        'document_bon_paiement': contrat.document_bon_paiement,
        'preuves': preuves,
        'police': getattr(contrat, 'police_assurance', None),
        'peut_activer': contrat.peut_etre_active,
    })


@internal_required
def contrat_create(request):
    from clients.models import Client
    from django.urls import reverse

    client_id = request.GET.get('client')
    client = Client.objects.filter(pk=client_id).first() if client_id else None

    if request.method == 'POST':
        client = get_object_or_404(Client, pk=request.POST.get('client_id'))
        form = ContratForm(request.POST, client=client)
        if form.is_valid():
            contrat = form.save(commit=False)
            contrat.client = client
            contrat.save()
            if not contrat.date_souscription:
                contrat.date_souscription = timezone.now()
                contrat.save(update_fields=['date_souscription', 'updated_at'])
            generate_contrat_pdf(contrat, request.user)
            generate_bon_paiement_pdf(contrat, request.user)
            log_client_activity(
                client, ActiviteClient.TypeActivite.CONTRAT_CREE,
                f'Contrat {contrat.reference} créé', request.user
            )
            if contrat.statut in (ContratStatut.BROUILLON, ContratStatut.EN_ATTENTE):
                create_pending_action(
                    user=request.user,
                    action_type='CONTRAT_NON_FINALISE',
                    title=f'Finaliser le contrat {contrat.reference}',
                    description='Complétez et activez le contrat.',
                    obj=contrat,
                )
            messages.success(request, 'Contrat créé.')
            return redirect('contrats:detail', pk=contrat.pk)
    else:
        form = ContratForm(client=client)

    clients = Client.objects.filter(is_active=True).select_related('user')
    return render(request, 'contrats/form_internal.html', {
        'form': form,
        'clients': clients,
        'selected_client': client,
        'title': 'Nouveau contrat',
        'back_url': reverse('contrats:list'),
        'client_select_url': reverse('contrats:create'),
        'help_steps': [
            'Sélectionnez le client',
            'Choisissez un bien validé',
            'Définissez les dates et la prime (USD)',
            'Activez après documents + paiement validés',
        ],
        'help_note': 'Préférez la déclaration de bien : police et contrat sont générés automatiquement.',
    })


@internal_required
def contrat_validate_paiement(request, pk):
    contrat = get_object_or_404(Contrat, pk=pk)
    if request.method != 'POST':
        return redirect('contrats:detail', pk=pk)

    preuve_id = request.POST.get('preuve_id')
    preuve = get_object_or_404(PreuvePaiement, pk=preuve_id, contrat=contrat)
    preuve.is_validated = True
    preuve.validee_par = request.user
    preuve.date_validation = timezone.now()
    preuve.save(update_fields=['is_validated', 'validee_par', 'date_validation'])

    contrat.paiement_valide = True
    contrat.save(update_fields=['paiement_valide', 'updated_at'])

    create_notification(
        user=contrat.client.user,
        notif_type='STATUT_CHANGE',
        title=f'Paiement validé — {contrat.reference}',
        message='Votre preuve de paiement a été acceptée. Le contrat pourra être activé.',
        obj=contrat,
    )
    messages.success(request, 'Paiement validé.')
    return redirect('contrats:detail', pk=pk)


@internal_required
def contrat_activate(request, pk):
    contrat = get_object_or_404(Contrat, pk=pk)
    if request.method == 'POST':
        if not contrat.paiement_valide:
            messages.error(request, 'Le paiement doit être validé avant activation.')
            return redirect('contrats:detail', pk=pk)
        if not contrat.documents_requis_complets:
            messages.error(request, 'Des documents justificatifs du bien sont encore manquants.')
            return redirect('contrats:detail', pk=pk)
        if contrat.bien.statut != 'VALIDE':
            messages.error(request, 'Le bien doit être validé avant activation du contrat.')
            return redirect('contrats:detail', pk=pk)

        contrat.statut = ContratStatut.ACTIF
        contrat.save(update_fields=['statut', 'updated_at'])
        resolve_pending_for_object(contrat, action_type=ActionType.CONTRAT_NON_FINALISE)
        resolve_pending_for_object(contrat.bien, action_type='DOCUMENTS_MANQUANTS')
        create_notification(
            user=contrat.client.user,
            notif_type='STATUT_CHANGE',
            title=f'Contrat {contrat.reference} activé',
            message='Votre contrat est maintenant actif.',
            obj=contrat,
        )
        messages.success(request, 'Contrat activé.')
    return redirect('contrats:detail', pk=pk)
