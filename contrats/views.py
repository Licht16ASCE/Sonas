from datetime import date, timedelta

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.decorators import client_required, internal_required
from core.filters import FILTER_CHOICES, get_active_filter
from clients.models import ActiviteClient
from clients.services import log_client_activity
from notifications.models import ActionType
from notifications.services import (
    create_notification,
    create_pending_action,
    notify_staff,
    resolve_pending_for_object,
)
from .forms import ClientContratForm, ContratForm
from .models import Contrat, ContratStatut
from .services import generate_contrat_pdf, get_biens_metadata


@client_required
def contrat_list_client(request):
    client = request.user.client_profile
    contrats = Contrat.objects.filter(client=client).select_related('bien')
    return render(request, 'contrats/list_client.html', {'contrats': contrats})


@client_required
def contrat_detail_client(request, pk):
    client = request.user.client_profile
    contrat = get_object_or_404(
        Contrat.objects.select_related('bien'),
        pk=pk, client=client,
    )
    sinistres = contrat.sinistres.all()[:5]
    return render(request, 'contrats/detail.html', {
        'contrat': contrat,
        'sinistres': sinistres,
        'show_next_steps': True,
        'document_contrat': contrat.document_contractuel,
    })


@client_required
def contrat_create_client(request):
    """Souscription via contrat visuel — PDF puis consolidation documentaire."""
    client = request.user.client_profile
    contrat_preview = Contrat(client=client)

    if request.method == 'POST':
        form = ClientContratForm(request.POST, client=client)
        if form.is_valid():
            contrat = form.save(commit=False)
            contrat.client = client
            contrat.statut = ContratStatut.BROUILLON
            contrat.date_souscription = timezone.now()
            contrat.save()

            generate_contrat_pdf(contrat, request.user)

            log_client_activity(
                client, ActiviteClient.TypeActivite.CONTRAT_CREE,
                f'Souscription contrat {contrat.reference} (contrat visuel signé)',
                request.user,
            )
            create_notification(
                user=request.user,
                notif_type='STATUT_CHANGE',
                title=f'Contrat {contrat.reference} enregistré',
                message='Votre contrat a été généré au format PDF. Complétez le dossier avec vos justificatifs.',
                obj=contrat,
            )
            create_pending_action(
                user=request.user,
                action_type='DOCUMENTS_MANQUANTS',
                title=f'Consolider le dossier {contrat.reference}',
                description='Ajoutez les justificatifs complémentaires pour votre contrat.',
                obj=contrat.bien,
            )
            notify_staff(
                title=f'Contrat {contrat.reference} à activer',
                message=f'{client.display_name} a signé un contrat visuel pour {contrat.bien.reference}.',
                obj=contrat,
                pending_action_type=ActionType.CONTRAT_NON_FINALISE,
                pending_title=f'Activer le contrat {contrat.reference}',
                pending_description=f'Client : {client.display_name} — PDF contractuel disponible',
            )
            messages.success(request, 'Contrat signé et enregistré. Ajoutez vos documents complémentaires.')
            return redirect('contrats_client:consolidation', pk=contrat.pk)
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
            'Signer (génération PDF)',
            'Ajouter les documents',
            'Activation par un agent',
        ],
        'guide_tip': (
            f'{biens_eligibles} bien{"s" if biens_eligibles > 1 else ""} éligible{"s" if biens_eligibles > 1 else ""}. '
            'Les champs en encadré sont les seules zones à modifier. '
            'Vérifiez le plafond d\'indemnisation avant signature.'
        ),
    })


@client_required
def contrat_consolidation_client(request, pk):
    """Étape post-signature : upload des documents pour consolider le dossier."""
    client = request.user.client_profile
    contrat = get_object_or_404(
        Contrat.objects.select_related('bien'),
        pk=pk, client=client,
    )
    documents_bien = contrat.bien.documents.exclude(
        type_document='CONTRAT_PDF',
    ).order_by('-created_at')[:10]
    return render(request, 'contrats/consolidation.html', {
        'contrat': contrat,
        'document_contrat': contrat.document_contractuel,
        'documents_bien': documents_bien,
        'guide_steps': [
            'Lire et compléter le contrat',
            'Signer (génération PDF)',
            'Ajouter les documents',
            'Activation par un agent',
        ],
        'guide_tip': 'Ajoutez titre de propriété, bail ou état des lieux pour accélérer l\'activation du contrat.',
    })


@internal_required
def contrat_list(request):
    filter_key = get_active_filter(request)
    qs = Contrat.objects.select_related('client', 'client__user', 'bien')

    if filter_key == 'en_attente':
        qs = qs.filter(statut=ContratStatut.BROUILLON)
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
        Contrat.objects.select_related('client', 'client__user', 'bien'), pk=pk
    )
    sinistres = contrat.sinistres.all()
    return render(request, 'contrats/detail_internal.html', {
        'contrat': contrat,
        'sinistres': sinistres,
        'document_contrat': contrat.document_contractuel,
    })


@internal_required
def contrat_create(request):
    from clients.models import Client
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
            log_client_activity(
                client, ActiviteClient.TypeActivite.CONTRAT_CREE,
                f'Contrat {contrat.reference} créé', request.user
            )
            if contrat.statut == ContratStatut.BROUILLON:
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
    from django.urls import reverse
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
            'Définissez les dates et la prime',
            'Activez le contrat depuis la fiche contrat',
        ],
        'help_note': 'Seuls les biens au statut validé sont proposés à la souscription.',
    })


@internal_required
def contrat_activate(request, pk):
    contrat = get_object_or_404(Contrat, pk=pk)
    if request.method == 'POST':
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
