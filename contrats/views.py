from datetime import date, timedelta

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from core.decorators import client_required, internal_required
from core.filters import FILTER_CHOICES, get_active_filter
from clients.models import ActiviteClient
from clients.services import log_client_activity
from notifications.services import create_notification, create_pending_action, resolve_pending_for_object
from .forms import ClientContratForm, ContratForm
from .models import Contrat, ContratStatut


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
    })


@client_required
def contrat_create_client(request):
    """Souscription contrat — brouillon en attente d'activation par un agent."""
    client = request.user.client_profile
    if request.method == 'POST':
        form = ClientContratForm(request.POST, client=client)
        if form.is_valid():
            contrat = form.save(commit=False)
            contrat.client = client
            contrat.statut = ContratStatut.BROUILLON
            contrat.save()
            log_client_activity(
                client, ActiviteClient.TypeActivite.CONTRAT_CREE,
                f'Souscription contrat {contrat.reference} (en attente d\'activation)',
                request.user,
            )
            create_notification(
                user=request.user,
                notif_type='STATUT_CHANGE',
                title=f'Demande de contrat {contrat.reference}',
                message='Votre souscription a été enregistrée. Un agent va l\'activer prochainement.',
                obj=contrat,
            )
            create_pending_action(
                user=request.user,
                action_type='CONTRAT_NON_FINALISE',
                title=f'Contrat {contrat.reference} en attente d\'activation',
                description='Un agent va valider votre souscription.',
                obj=contrat,
            )
            messages.success(request, 'Souscription enregistrée. En attente d\'activation.')
            return redirect('contrats_client:detail', pk=contrat.pk)
    else:
        form = ClientContratForm(client=client)

    biens_eligibles = form.fields['bien'].queryset.count()
    biens_en_attente = client.biens.filter(statut='EN_ATTENTE').count()
    return render(request, 'contrats/form_client.html', {
        'form': form,
        'title': 'Souscrire un contrat',
        'biens_eligibles': biens_eligibles,
        'biens_en_attente': biens_en_attente,
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
    return render(request, 'contrats/form_internal.html', {
        'form': form,
        'clients': clients,
        'selected_client': client,
        'title': 'Nouveau contrat',
    })


@internal_required
def contrat_activate(request, pk):
    contrat = get_object_or_404(Contrat, pk=pk)
    if request.method == 'POST':
        contrat.statut = ContratStatut.ACTIF
        contrat.save(update_fields=['statut', 'updated_at'])
        resolve_pending_for_object(contrat)
        create_notification(
            user=contrat.client.user,
            notif_type='STATUT_CHANGE',
            title=f'Contrat {contrat.reference} activé',
            message='Votre contrat est maintenant actif.',
            obj=contrat,
        )
        messages.success(request, 'Contrat activé.')
    return redirect('contrats:detail', pk=pk)
