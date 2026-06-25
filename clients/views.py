from django.contrib import messages
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render

from core.decorators import client_required, internal_required
from core.filters import FILTER_CHOICES, get_active_filter
from .forms import ClientCreateForm, ClientProfileForm
from .models import ActiviteClient, Client
from .services import log_client_activity


@client_required
def client_dashboard(request):
    """Dashboard espace client."""
    client = request.user.client_profile
    from biens.models import Bien
    from contrats.models import Contrat
    from sinistres.models import Sinistre
    from notifications.models import ActionEnAttente

    kpis = {
        'biens': Bien.objects.filter(client=client).count(),
        'contrats': Contrat.objects.filter(client=client, statut='ACTIF').count(),
        'sinistres': Sinistre.objects.filter(contrat__client=client).count(),
    }

    pending = ActionEnAttente.objects.filter(user=request.user, is_resolved=False)[:5]
    recent_activites = client.activites.all()[:5]

    return render(request, 'clients/dashboard_client.html', {
        'client': client,
        'kpis': kpis,
        'pending_actions': pending,
        'recent_activites': recent_activites,
    })


@client_required
def client_profile(request):
    client = request.user.client_profile
    if request.method == 'POST':
        form = ClientProfileForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            log_client_activity(
                client, ActiviteClient.TypeActivite.PROFIL_MODIFIE,
                'Profil mis à jour', request.user
            )
            messages.success(request, 'Profil mis à jour.')
            return redirect('clients_client:profile')
    else:
        form = ClientProfileForm(instance=client)
    return render(request, 'clients/profile.html', {'form': form, 'client': client})


@client_required
def client_activites(request):
    client = request.user.client_profile
    activites = client.activites.all()
    return render(request, 'clients/activites.html', {
        'client': client,
        'activites': activites,
    })


# --- Vues internes ---

@internal_required
def client_list(request):
    qs = Client.objects.select_related('user').filter(is_active=True)
    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(
            models.Q(raison_sociale__icontains=search) |
            models.Q(user__first_name__icontains=search) |
            models.Q(user__last_name__icontains=search) |
            models.Q(user__email__icontains=search)
        )
    return render(request, 'clients/list_internal.html', {
        'clients': qs,
        'search': search,
        'filter_choices': FILTER_CHOICES,
        'active_filter': get_active_filter(request),
    })


@internal_required
def client_detail(request, pk):
    client = get_object_or_404(Client.objects.select_related('user'), pk=pk)
    activites = client.activites.all()[:20]
    biens = client.biens.all()
    contrats = client.contrats.select_related('bien').all()
    return render(request, 'clients/detail_internal.html', {
        'client': client,
        'activites': activites,
        'biens': biens,
        'contrats': contrats,
    })


@internal_required
def client_create(request):
    if request.method == 'POST':
        form = ClientCreateForm(request.POST)
        if form.is_valid():
            client = form.save()
            log_client_activity(
                client, ActiviteClient.TypeActivite.AUTRE,
                'Compte client créé par un agent', request.user
            )
            messages.success(request, f'Client {client.display_name} créé.')
            return redirect('clients_internal:detail', pk=client.pk)
    else:
        form = ClientCreateForm()
    return render(request, 'clients/form_internal.html', {'form': form, 'title': 'Nouveau client'})


@internal_required
def client_edit(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if request.method == 'POST':
        form = ClientProfileForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, 'Client mis à jour.')
            return redirect('clients_internal:detail', pk=client.pk)
    else:
        form = ClientProfileForm(instance=client)
    return render(request, 'clients/form_internal.html', {
        'form': form,
        'client': client,
        'title': f'Modifier {client.display_name}',
    })
