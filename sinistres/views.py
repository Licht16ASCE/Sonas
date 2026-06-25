from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import UserRole
from core.decorators import client_required, gerant_or_admin_required, internal_required
from core.filters import FILTER_CHOICES, apply_status_filter, get_active_filter
from clients.models import ActiviteClient
from clients.services import log_client_activity
from notifications.services import create_notification, create_pending_action, resolve_pending_for_object
from .forms import SinistreForm, SinistreValidationForm
from .models import Sinistre, SinistreStatut


def _apply_sinistre_filters(qs, filter_key):
    if filter_key == 'en_attente':
        return qs.filter(statut=SinistreStatut.DECLARE)
    if filter_key == 'urgents':
        return qs.filter(is_urgent=True)
    if filter_key == 'docs_manquants':
        return qs.filter(documents__isnull=True).distinct()
    mapping = {
        'en_cours': SinistreStatut.EN_COURS,
        'valides': SinistreStatut.VALIDE,
        'rejetes': SinistreStatut.REJETE,
    }
    if filter_key in mapping:
        return qs.filter(statut=mapping[filter_key])
    return qs


@client_required
def sinistre_list_client(request):
    client = request.user.client_profile
    sinistres = Sinistre.objects.filter(contrat__client=client).select_related('contrat', 'contrat__bien')
    return render(request, 'sinistres/list_client.html', {'sinistres': sinistres})


@client_required
def sinistre_create_client(request):
    client = request.user.client_profile
    if request.method == 'POST':
        form = SinistreForm(request.POST, client=client)
        if form.is_valid():
            sinistre = form.save(commit=False)
            sinistre.declare_par = request.user
            sinistre.statut = SinistreStatut.DECLARE
            sinistre.save()
            log_client_activity(
                client, ActiviteClient.TypeActivite.SINISTRE_DECLARE,
                f'Sinistre {sinistre.reference} déclaré', request.user
            )
            create_pending_action(
                user=request.user,
                action_type='SINISTRE_INCOMPLET',
                title=f'Compléter le sinistre {sinistre.reference}',
                description='Ajoutez les documents justificatifs.',
                obj=sinistre,
            )
            create_notification(
                user=request.user,
                notif_type='STATUT_CHANGE',
                title='Sinistre déclaré',
                message=f'Votre sinistre {sinistre.reference} a été enregistré.',
                obj=sinistre,
            )
            messages.success(request, 'Sinistre déclaré.')
            return redirect('sinistres_client:detail', pk=sinistre.pk)
    else:
        form = SinistreForm(client=client)
    from core.forms import apply_form_styles
    apply_form_styles(form)
    return render(request, 'sinistres/form.html', {'form': form, 'title': 'Déclarer un sinistre'})


@client_required
def sinistre_detail_client(request, pk):
    client = request.user.client_profile
    sinistre = get_object_or_404(
        Sinistre.objects.select_related('contrat', 'contrat__bien'),
        pk=pk, contrat__client=client
    )
    return render(request, 'sinistres/detail.html', {'sinistre': sinistre})


@internal_required
def sinistre_list(request):
    filter_key = get_active_filter(request)
    qs = Sinistre.objects.select_related(
        'contrat', 'contrat__client', 'contrat__client__user', 'contrat__bien'
    )
    qs = _apply_sinistre_filters(qs, filter_key)
    search = request.GET.get('q', '').strip()
    if search:
        from django.db import models
        qs = qs.filter(
            models.Q(reference__icontains=search) |
            models.Q(contrat__client__raison_sociale__icontains=search) |
            models.Q(contrat__client__user__first_name__icontains=search) |
            models.Q(contrat__client__user__last_name__icontains=search)
        )
    return render(request, 'sinistres/list_internal.html', {
        'sinistres': qs,
        'search': search,
        'filter_choices': FILTER_CHOICES,
        'active_filter': filter_key,
    })


@internal_required
def sinistre_detail(request, pk):
    sinistre = get_object_or_404(
        Sinistre.objects.select_related('contrat', 'contrat__client', 'contrat__bien'),
        pk=pk
    )
    validation_form = SinistreValidationForm(instance=sinistre)
    can_validate = request.user.role in (UserRole.GERANT, UserRole.ADMIN)
    return render(request, 'sinistres/detail_internal.html', {
        'sinistre': sinistre,
        'validation_form': validation_form,
        'can_validate': can_validate,
    })


@internal_required
def sinistre_create(request):
    from clients.models import Client
    client_id = request.GET.get('client')
    client = Client.objects.filter(pk=client_id).first() if client_id else None

    if request.method == 'POST':
        client = get_object_or_404(Client, pk=request.POST.get('client_id'))
        form = SinistreForm(request.POST, client=client)
        if form.is_valid():
            sinistre = form.save(commit=False)
            sinistre.declare_par = request.user
            sinistre.save()
            messages.success(request, 'Sinistre créé.')
            return redirect('sinistres:detail', pk=sinistre.pk)
    else:
        form = SinistreForm(client=client)

    clients = Client.objects.filter(is_active=True).select_related('user')
    return render(request, 'sinistres/form_internal.html', {
        'form': form,
        'clients': clients,
        'selected_client': client,
        'title': 'Nouveau sinistre',
    })


@internal_required
def sinistre_update_status(request, pk):
    sinistre = get_object_or_404(Sinistre, pk=pk)
    new_statut = request.POST.get('statut')

    # Transition vers EN_COURS — agent/gérant/admin
    if new_statut == SinistreStatut.EN_COURS:
        sinistre.statut = SinistreStatut.EN_COURS
        sinistre.save(update_fields=['statut', 'updated_at'])
        create_notification(
            user=sinistre.client.user,
            notif_type='STATUT_CHANGE',
            title=f'Sinistre {sinistre.reference} en cours de traitement',
            message='Un agent traite votre dossier.',
            obj=sinistre,
        )
        messages.success(request, 'Sinistre passé en cours.')

    return redirect('sinistres:detail', pk=pk)


@gerant_or_admin_required
def sinistre_validate(request, pk):
    """Validation finale — GERANT ou ADMIN uniquement."""
    sinistre = get_object_or_404(Sinistre, pk=pk)
    if request.method == 'POST':
        form = SinistreValidationForm(request.POST, instance=sinistre)
        if form.is_valid():
            sinistre = form.save(commit=False)
            if sinistre.statut in (SinistreStatut.VALIDE, SinistreStatut.REJETE):
                sinistre.valide_par = request.user
                sinistre.date_validation = timezone.now()
            sinistre.save()
            resolve_pending_for_object(sinistre)
            create_notification(
                user=sinistre.client.user,
                notif_type='STATUT_CHANGE',
                title=f'Décision sur sinistre {sinistre.reference}',
                message=f'Statut final : {sinistre.get_statut_display()}',
                obj=sinistre,
                priority='high' if sinistre.statut == SinistreStatut.REJETE else 'normal',
            )
            messages.success(request, 'Décision enregistrée.')
            return redirect('sinistres:detail', pk=pk)
    return redirect('sinistres:detail', pk=pk)
