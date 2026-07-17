from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import UserRole
from core.decorators import client_required, internal_required
from core.filters import FILTER_CHOICES, apply_status_filter, get_active_filter
from clients.models import ActiviteClient
from clients.services import log_client_activity
from notifications.services import (
    create_notification,
    create_pending_action,
    notify_staff,
    resolve_pending_for_object,
)
from notifications.models import ActionType
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
            from contrats.workflow import generer_police_et_contrat
            contrat, police = generer_police_et_contrat(bien, request.user, grille=bien.grille_tarifaire)
            log_client_activity(
                client, ActiviteClient.TypeActivite.BIEN_CREE,
                f'Bien déclaré : {bien.reference} — contrat {contrat.reference} / police {police.reference}',
                request.user
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
                message=(
                    f'Votre bien {bien.reference} est en attente de validation. '
                    f'Contrat {contrat.reference} et bon de paiement générés automatiquement.'
                ),
                obj=bien,
            )
            notify_staff(
                title=f'Bien {bien.reference} à valider',
                message=f'{client.display_name} a déclaré un bien ({bien.ville}).',
                obj=bien,
                pending_action_type=ActionType.BIEN_A_VALIDER,
                pending_title=f'Valider le bien {bien.reference}',
                pending_description=f'Client : {client.display_name} — {bien.adresse}, {bien.ville}',
            )
            messages.success(
                request,
                'Bien déclaré. Police, contrat (en attente) et bon de paiement générés. '
                'Téléchargez le bon, payez en banque puis déposez la preuve.',
            )
            return redirect('contrats_client:detail', pk=contrat.pk)
    else:
        form = BienForm()
    return render(request, 'biens/form.html', {
        'form': form,
        'title': 'Déclarer un bien',
        'guide_steps': [
            'Vous déclarez le bien',
            'Police + contrat + bon de paiement générés',
            'Vous uploadez justificatifs et preuve de paiement',
            'Un agent valide le bien et le paiement',
        ],
        'guide_tip': 'La valeur estimée (USD) et le forfait déterminent automatiquement la prime. Après déclaration, téléchargez le bon de paiement.',
    })


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
        statut__in=(ContratStatut.EN_ATTENTE, ContratStatut.BROUILLON, ContratStatut.ACTIF),
    ).first()
    peut_souscrire = False
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
    from django.urls import reverse
    client_id = request.GET.get('client')
    client = Client.objects.filter(pk=client_id).first() if client_id else None

    if request.method == 'POST':
        form = BienForm(request.POST)
        client = get_object_or_404(Client, pk=request.POST.get('client_id'))
        if form.is_valid():
            bien = form.save(commit=False)
            bien.client = client
            bien.save()
            from contrats.workflow import generer_police_et_contrat
            generer_police_et_contrat(bien, request.user, grille=bien.grille_tarifaire)
            if bien.statut == BienStatut.EN_ATTENTE:
                notify_staff(
                    title=f'Bien {bien.reference} à valider',
                    message=f'Bien créé pour {client.display_name}.',
                    obj=bien,
                    pending_action_type=ActionType.BIEN_A_VALIDER,
                    pending_title=f'Valider le bien {bien.reference}',
                    pending_description=f'Client : {client.display_name}',
                    exclude_user=request.user,
                )
            messages.success(request, 'Bien créé — police, contrat et bon de paiement générés.')
            return redirect('biens:detail', pk=bien.pk)
    else:
        form = BienForm()

    clients = Client.objects.filter(is_active=True).select_related('user')
    return render(request, 'biens/form_internal.html', {
        'form': form,
        'clients': clients,
        'selected_client': client,
        'title': 'Nouveau bien',
        'back_url': reverse('biens:list'),
        'client_select_url': reverse('biens:create'),
        'help_steps': [
            'Sélectionnez le client propriétaire',
            'Renseignez l\'adresse, la valeur (USD) et le forfait',
            'Police + contrat EN ATTENTE + bon de paiement générés',
            'Le client dépose preuve de paiement et justificatifs',
        ],
        'help_note': 'Le contrat reste en attente jusqu\'à documents + paiement validés.',
    })


@internal_required
def bien_validate(request, pk):
    bien = get_object_or_404(Bien, pk=pk)
    if request.method == 'POST':
        form = BienValidationForm(request.POST, instance=bien)
        if form.is_valid():
            old_statut = bien.statut
            bien = form.save()
            resolve_pending_for_object(bien, action_type=ActionType.BIEN_A_VALIDER)
            resolve_pending_for_object(bien, action_type=ActionType.BIEN_INCOMPLET)
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
