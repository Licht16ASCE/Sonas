from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import UserRole
from core.decorators import client_required, internal_required
from core.filters import FILTER_CHOICES, apply_status_filter, get_active_filter
from clients.models import ActiviteClient
from clients.services import log_client_activity
from notifications.services import create_notification, create_pending_action, resolve_pending_for_object
from .forms import BienForm, BienValidationForm
from .models import Bien, BienStatut


def _apply_bien_filters(qs, filter_key):
    if filter_key == 'urgents':
        return qs.filter(statut=BienStatut.EN_ATTENTE)
    if filter_key == 'docs_manquants':
        return qs.filter(documents__isnull=True).distinct()
    return apply_status_filter(qs, 'statut', filter_key)


@client_required
def bien_list_client(request):
    client = request.user.client_profile
    biens = Bien.objects.filter(client=client)
    return render(request, 'biens/list_client.html', {'biens': biens})


@client_required
def bien_create_client(request):
    client = request.user.client_profile
    if request.method == 'POST':
        form = BienForm(request.POST)
        if form.is_valid():
            bien = form.save(commit=False)
            bien.client = client
            bien.statut = BienStatut.EN_ATTENTE
            bien.save()
            log_client_activity(
                client, ActiviteClient.TypeActivite.BIEN_CREE,
                f'Bien déclaré : {bien.reference}', request.user
            )
            create_pending_action(
                user=request.user,
                action_type='BIEN_INCOMPLET',
                title='Finaliser la déclaration du bien',
                description=f'Complétez les documents pour {bien.reference}',
                obj=bien,
            )
            create_notification(
                user=request.user,
                notif_type='STATUT_CHANGE',
                title='Bien déclaré',
                message=f'Votre bien {bien.reference} est en attente de validation.',
                obj=bien,
            )
            messages.success(request, 'Bien déclaré avec succès. Ajoutez vos documents justificatifs.')
            return redirect('biens_client:detail', pk=bien.pk)
    else:
        form = BienForm()
    return render(request, 'biens/form.html', {'form': form, 'title': 'Déclarer un bien'})


@client_required
def bien_detail_client(request, pk):
    client = request.user.client_profile
    bien = get_object_or_404(
        Bien.objects.prefetch_related('documents'),
        pk=pk, client=client,
    )
    from contrats.models import Contrat, ContratStatut
    contrat_actif = Contrat.objects.filter(
        client=client, bien=bien,
        statut__in=(ContratStatut.BROUILLON, ContratStatut.ACTIF),
    ).first()
    peut_souscrire = (
        bien.statut == BienStatut.VALIDE
        and not contrat_actif
    )
    return render(request, 'biens/detail.html', {
        'bien': bien,
        'contrat_actif': contrat_actif,
        'peut_souscrire': peut_souscrire,
        'show_next_steps': True,
    })


@internal_required
def bien_list(request):
    filter_key = get_active_filter(request)
    qs = Bien.objects.select_related('client', 'client__user')
    qs = _apply_bien_filters(qs, filter_key)
    search = request.GET.get('q', '').strip()
    if search:
        from django.db import models
        qs = qs.filter(
            models.Q(reference__icontains=search) |
            models.Q(client__raison_sociale__icontains=search) |
            models.Q(client__user__first_name__icontains=search) |
            models.Q(client__user__last_name__icontains=search)
        )
    return render(request, 'biens/list_internal.html', {
        'biens': qs,
        'search': search,
        'filter_choices': FILTER_CHOICES,
        'active_filter': filter_key,
    })


@internal_required
def bien_detail(request, pk):
    bien = get_object_or_404(Bien.objects.select_related('client', 'client__user'), pk=pk)
    validation_form = BienValidationForm(instance=bien)
    return render(request, 'biens/detail_internal.html', {
        'bien': bien,
        'validation_form': validation_form,
    })


@internal_required
def bien_create(request):
    from clients.models import Client
    if request.method == 'POST':
        form = BienForm(request.POST)
        client_id = request.POST.get('client_id')
        client = get_object_or_404(Client, pk=client_id)
        if form.is_valid():
            bien = form.save(commit=False)
            bien.client = client
            bien.save()
            messages.success(request, 'Bien créé.')
            return redirect('biens:detail', pk=bien.pk)
    else:
        form = BienForm()
    from clients.models import Client
    clients = Client.objects.filter(is_active=True).select_related('user')
    return render(request, 'biens/form_internal.html', {
        'form': form,
        'clients': clients,
        'title': 'Nouveau bien',
    })


@internal_required
def bien_validate(request, pk):
    bien = get_object_or_404(Bien, pk=pk)
    if request.method == 'POST':
        form = BienValidationForm(request.POST, instance=bien)
        if form.is_valid():
            old_statut = bien.statut
            bien = form.save()
            resolve_pending_for_object(bien)
            create_notification(
                user=bien.client.user,
                notif_type='STATUT_CHANGE',
                title=f'Statut bien {bien.reference}',
                message=f'Votre bien est passé au statut : {bien.get_statut_display()}',
                obj=bien,
            )
            messages.success(request, 'Statut mis à jour.')
            return redirect('biens:detail', pk=bien.pk)
    return redirect('biens:detail', pk=pk)
