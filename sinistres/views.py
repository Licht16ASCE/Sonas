from django import forms
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import UserRole
from core.decorators import client_required, gerant_or_admin_required, internal_required
from core.filters import FILTER_CHOICES, apply_status_filter, get_active_filter
from clients.models import ActiviteClient
from clients.services import log_client_activity
from notifications.services import (
    STAFF_ROLES_AGENTS,
    STAFF_ROLES_GERANTS,
    create_notification,
    create_pending_action,
    notify_staff,
    resolve_pending_for_object,
)
from notifications.models import ActionType
from documents.models import Document, DocumentType
from .forms import SinistreForm, SinistreTraitementForm, SinistreValidationForm
from .models import Sinistre, SinistreStatut
from .services import IndemnisationError, lancer_indemnisation


def _apply_sinistre_filters(qs, filter_key):
    if filter_key == 'en_attente':
        return qs.filter(statut=SinistreStatut.DECLARE)
    if filter_key == 'a_valider':
        return qs.filter(statut=SinistreStatut.EN_COURS, soumis_validation=True)
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
            notify_staff(
                roles=STAFF_ROLES_AGENTS,
                title=f'Nouveau sinistre {sinistre.reference}',
                message=f'{client.display_name} — {sinistre.get_type_sinistre_display()}',
                obj=sinistre,
                priority='high' if sinistre.is_urgent else 'normal',
                pending_action_type=ActionType.SINISTRE_A_TRAITER,
                pending_title=f'Traiter le sinistre {sinistre.reference}',
                pending_description=f'Client : {client.display_name} — contrat {sinistre.contrat.reference}',
            )
            messages.success(request, 'Sinistre déclaré.')
            return redirect('sinistres_client:detail', pk=sinistre.pk)
    else:
        form = SinistreForm(client=client)
    return render(request, 'sinistres/form.html', {
        'form': form,
        'title': 'Déclarer un sinistre',
        'guide_steps': [
            'Vous déclarez le sinistre',
            'Vous ajoutez les pièces justificatives',
            'Un agent traite le dossier',
            'Vous suivez l\'avancement en ligne',
        ],
        'guide_tip': 'Cochez la case « urgent » si le sinistre nécessite une prise en charge rapide (dégât des eaux, incendie…).',
    })


@client_required
def sinistre_detail_client(request, pk):
    client = request.user.client_profile
    sinistre = get_object_or_404(
        Sinistre.objects.select_related(
            'contrat', 'contrat__bien', 'document_retrait_bancaire', 'preuve_retrait_indemnisation',
        ).prefetch_related(
            'documents', 'rapports_indemnisation__document',
        ),
        pk=pk, contrat__client=client,
    )
    return render(request, 'sinistres/detail.html', {
        'sinistre': sinistre,
        'rapport': sinistre.rapport_indemnisation,
    })


@client_required
def sinistre_upload_preuve_retrait(request, pk):
    """Le client dépose la preuve de retrait bancaire → statut VERT."""
    from .models import StatutRetraitPaiement
    from django.core.files.base import ContentFile

    client = request.user.client_profile
    sinistre = get_object_or_404(Sinistre, pk=pk, contrat__client=client)
    if request.method != 'POST':
        return redirect('sinistres_client:detail', pk=pk)

    if not sinistre.montant_indemnise:
        messages.error(request, 'Aucune indemnisation enregistrée sur ce dossier.')
        return redirect('sinistres_client:detail', pk=pk)

    fichier = request.FILES.get('preuve_retrait')
    if not fichier:
        messages.error(request, 'Veuillez sélectionner un fichier.')
        return redirect('sinistres_client:detail', pk=pk)

    content = fichier.read()
    doc = Document(
        sinistre=sinistre,
        type_document=DocumentType.PREUVE_PAIEMENT,
        titre=f'Preuve de retrait — {sinistre.reference}',
        uploaded_by=request.user,
    )
    doc.fichier.save(fichier.name, ContentFile(content), save=True)

    sinistre.preuve_retrait_indemnisation = doc
    sinistre.statut_retrait_paiement = StatutRetraitPaiement.VERT
    sinistre.save(update_fields=[
        'preuve_retrait_indemnisation', 'statut_retrait_paiement', 'updated_at',
    ])
    create_notification(
        user=request.user,
        notif_type='STATUT_CHANGE',
        title=f'Preuve de retrait enregistrée — {sinistre.reference}',
        message='Votre preuve a été enregistrée. L\'état d\'indemnisation est passé au vert.',
        obj=sinistre,
    )
    messages.success(request, 'Preuve de retrait déposée — statut vert.')
    return redirect('sinistres_client:detail', pk=pk)


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
        'filter_choices': FILTER_CHOICES + [('a_valider', 'À valider (gérant)')],
        'active_filter': filter_key,
    })


def _sinistre_detail_context(request, sinistre, traitement_form=None, validation_form=None):
    """Contexte partagé pour la fiche sinistre interne."""
    if traitement_form is None:
        traitement_form = SinistreTraitementForm(instance=sinistre)
    if validation_form is None:
        validation_form = SinistreValidationForm(sinistre=sinistre)

    dossier_incomplet = (
        sinistre.soumis_validation and sinistre.indemnisation_accordee is None
    )
    can_traiter = (
        sinistre.statut == SinistreStatut.EN_COURS
        and (
            not sinistre.soumis_validation
            or dossier_incomplet
        )
        and request.user.role in (UserRole.AGENT, UserRole.GERANT, UserRole.ADMIN)
    )
    can_validate = (
        request.user.role in (UserRole.GERANT, UserRole.ADMIN)
        and sinistre.en_attente_validation_gerant
        and not dossier_incomplet
    )
    if sinistre.statut in (SinistreStatut.VALIDE, SinistreStatut.REJETE):
        workflow_step = 4
    elif sinistre.en_attente_validation_gerant and not dossier_incomplet:
        workflow_step = 3
    elif sinistre.statut == SinistreStatut.EN_COURS:
        workflow_step = 2
    else:
        workflow_step = 1
    return {
        'sinistre': sinistre,
        'traitement_form': traitement_form if can_traiter else None,
        'validation_form': validation_form if can_validate else None,
        'can_traiter': can_traiter,
        'can_validate': can_validate,
        'dossier_incomplet': dossier_incomplet,
        'rapport': sinistre.rapport_indemnisation,
        'workflow_steps': [
            'Déclaration client',
            'Traitement agent',
            'Validation gérant',
            'Clôture & rapport',
        ],
        'workflow_step': workflow_step,
        'workflow_tip': (
            'L\'agent transmet sa décision d\'indemnisation ; '
            'seul le gérant valide et clôture le sinistre.'
        ),
    }


@internal_required
def sinistre_detail(request, pk):
    sinistre = get_object_or_404(
        Sinistre.objects.select_related(
            'contrat', 'contrat__client', 'contrat__bien',
        ).prefetch_related('documents', 'rapports_indemnisation__document'),
        pk=pk,
    )
    return render(request, 'sinistres/detail_internal.html', _sinistre_detail_context(request, sinistre))


@internal_required
def sinistre_create(request):
    from clients.models import Client
    from django.urls import reverse
    client_id = request.GET.get('client')
    client = Client.objects.filter(pk=client_id).first() if client_id else None

    if request.method == 'POST':
        client = get_object_or_404(Client, pk=request.POST.get('client_id'))
        form = SinistreForm(request.POST, client=client)
        if form.is_valid():
            sinistre = form.save(commit=False)
            sinistre.declare_par = request.user
            sinistre.save()
            if sinistre.statut == SinistreStatut.DECLARE:
                notify_staff(
                    roles=STAFF_ROLES_AGENTS,
                    title=f'Nouveau sinistre {sinistre.reference}',
                    message=f'Sinistre créé pour {client.display_name}.',
                    obj=sinistre,
                    priority='high' if sinistre.is_urgent else 'normal',
                    pending_action_type=ActionType.SINISTRE_A_TRAITER,
                    pending_title=f'Traiter le sinistre {sinistre.reference}',
                    pending_description=f'Client : {client.display_name}',
                    exclude_user=request.user,
                )
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
        'back_url': reverse('sinistres:list'),
        'client_select_url': reverse('sinistres:create'),
        'help_steps': [
            'Sélectionnez le client concerné',
            'Choisissez le contrat actif (bien associé)',
            'Décrivez le sinistre, la date et le montant estimé',
            'Marquez comme urgent si nécessaire',
        ],
        'help_note': 'Seuls les contrats actifs et non bloqués apparaissent dans la liste.',
    })


@internal_required
def sinistre_update_status(request, pk):
    sinistre = get_object_or_404(Sinistre, pk=pk)
    new_statut = request.POST.get('statut')

    # Transition vers EN_COURS — agent/gérant/admin
    if new_statut == SinistreStatut.EN_COURS:
        sinistre.statut = SinistreStatut.EN_COURS
        sinistre.save(update_fields=['statut', 'updated_at'])
        resolve_pending_for_object(sinistre, action_type=ActionType.SINISTRE_A_TRAITER)
        resolve_pending_for_object(sinistre, action_type=ActionType.SINISTRE_INCOMPLET)
        create_notification(
            user=sinistre.client.user,
            notif_type='STATUT_CHANGE',
            title=f'Sinistre {sinistre.reference} en cours de traitement',
            message='Un agent traite votre dossier.',
            obj=sinistre,
        )
        messages.success(request, 'Sinistre passé en cours.')

    return redirect('sinistres:detail', pk=pk)


@internal_required
def sinistre_traiter(request, pk):
    """L'agent indique si une indemnisation est accordée et transmet au gérant."""
    sinistre = get_object_or_404(Sinistre, pk=pk)
    dossier_incomplet = (
        sinistre.soumis_validation and sinistre.indemnisation_accordee is None
    )
    if sinistre.statut != SinistreStatut.EN_COURS:
        messages.error(request, 'Ce sinistre ne peut pas être traité dans l\'état actuel.')
        return redirect('sinistres:detail', pk=pk)
    if sinistre.soumis_validation and not dossier_incomplet:
        messages.error(request, 'Ce dossier a déjà été transmis au gérant.')
        return redirect('sinistres:detail', pk=pk)

    if request.method != 'POST':
        return redirect('sinistres:detail', pk=pk)

    form = SinistreTraitementForm(request.POST, instance=sinistre)
    if not form.is_valid():
        messages.error(request, form.errors.as_text())
        ctx = _sinistre_detail_context(request, sinistre, traitement_form=form)
        return render(request, 'sinistres/detail_internal.html', ctx)

    sinistre = form.save(commit=False)
    sinistre.traite_par = request.user
    sinistre.soumis_validation = True
    sinistre.date_soumission = timezone.now()
    sinistre.save()

    resolve_pending_for_object(sinistre, action_type=ActionType.SINISTRE_A_TRAITER)

    if sinistre.indemnisation_accordee:
        desc = (
            f'Indemnisation proposée : {sinistre.montant_indemnisation_propose:.2f} $ — '
            f'Client : {sinistre.client.display_name}'
        )
    else:
        desc = f'Clôture sans indemnisation — Client : {sinistre.client.display_name}'

    notify_staff(
        roles=STAFF_ROLES_GERANTS,
        title=f'Sinistre {sinistre.reference} à valider',
        message=desc,
        obj=sinistre,
        priority='high' if sinistre.is_urgent else 'normal',
        pending_action_type=ActionType.SINISTRE_A_VALIDER,
        pending_title=f'Valider le sinistre {sinistre.reference}',
        pending_description=desc,
    )

    create_notification(
        user=sinistre.client.user,
        notif_type='STATUT_CHANGE',
        title=f'Sinistre {sinistre.reference} — validation en cours',
        message='Votre dossier a été examiné et est en attente de validation par un gérant.',
        obj=sinistre,
    )

    if sinistre.indemnisation_accordee:
        messages.success(
            request,
            f'Dossier transmis au gérant avec indemnisation proposée de '
            f'{sinistre.montant_indemnisation_propose:.2f} $.',
        )
    else:
        messages.success(request, 'Dossier transmis au gérant (sans indemnisation).')

    return redirect('sinistres:detail', pk=pk)


@gerant_or_admin_required
@transaction.atomic
def sinistre_validate(request, pk):
    """Clôture finale — gérant ou admin uniquement."""
    sinistre = get_object_or_404(Sinistre, pk=pk)
    if request.method != 'POST':
        return redirect('sinistres:detail', pk=pk)

    action = request.POST.get('action')
    form = SinistreValidationForm(request.POST, sinistre=sinistre)

    if action not in ('cloturer', 'rejeter'):
        messages.error(request, 'Action de clôture non reconnue.')
        return redirect('sinistres:detail', pk=pk)

    if not form.is_valid():
        messages.error(request, f'Clôture impossible : {form.errors.as_text()}')
        ctx = _sinistre_detail_context(request, sinistre, validation_form=form)
        ctx['can_validate'] = request.user.role in (UserRole.GERANT, UserRole.ADMIN)
        return render(request, 'sinistres/detail_internal.html', ctx)

    try:
        if action == 'cloturer':
            form.validate_cloture()
            statut = SinistreStatut.VALIDE
        else:
            form.validate_rejet()
            statut = SinistreStatut.REJETE
    except forms.ValidationError as exc:
        messages.error(request, exc.messages[0] if hasattr(exc, 'messages') else str(exc))
        ctx = _sinistre_detail_context(request, sinistre, validation_form=form)
        ctx['can_validate'] = request.user.role in (UserRole.GERANT, UserRole.ADMIN)
        return render(request, 'sinistres/detail_internal.html', ctx)

    sinistre.statut = statut
    sinistre.valide_par = request.user
    sinistre.date_validation = timezone.now()
    if statut == SinistreStatut.REJETE:
        sinistre.motif_rejet = form.cleaned_data['motif_rejet']
        sinistre.soumis_validation = False
    sinistre.save()

    resolve_pending_for_object(sinistre, action_type=ActionType.SINISTRE_A_VALIDER)
    resolve_pending_for_object(sinistre, action_type=ActionType.SINISTRE_A_TRAITER)
    resolve_pending_for_object(sinistre, action_type=ActionType.SINISTRE_INCOMPLET)

    if statut == SinistreStatut.VALIDE:
        if sinistre.indemnisation_accordee:
            try:
                rapport = lancer_indemnisation(
                    sinistre,
                    sinistre.montant_indemnisation_propose,
                    request.user,
                )
                messages.success(
                    request,
                    f'Sinistre clôturé. Indemnisation de {rapport.montant_indemnise:.2f} $ — '
                    f'rapport {rapport.reference} généré.',
                )
            except IndemnisationError as exc:
                messages.error(request, str(exc))
                raise
        else:
            create_notification(
                user=sinistre.client.user,
                notif_type='STATUT_CHANGE',
                title=f'Sinistre {sinistre.reference} clôturé',
                message=(
                    'Votre sinistre a été clôturé sans indemnisation. '
                    'Aucun montant n\'a été déduit de votre contrat.'
                ),
                obj=sinistre,
            )
            messages.success(
                request,
                'Sinistre clôturé sans indemnisation — aucune déduction sur le contrat.',
            )
    else:
        create_notification(
            user=sinistre.client.user,
            notif_type='STATUT_CHANGE',
            title=f'Décision sur sinistre {sinistre.reference}',
            message=f'Statut final : {sinistre.get_statut_display()}. {sinistre.motif_rejet}',
            obj=sinistre,
            priority='high',
        )
        messages.success(request, 'Sinistre rejeté.')
    return redirect('sinistres:detail', pk=pk)


@login_required
def rapport_indemnisation_detail(request, pk):
    from .models import RapportIndemnisation
    rapport = get_object_or_404(
        RapportIndemnisation.objects.select_related(
            'sinistre', 'sinistre__contrat', 'sinistre__contrat__client', 'document',
        ),
        pk=pk,
    )
    sinistre = rapport.sinistre
    if request.user.is_client:
        if sinistre.client.user_id != request.user.pk:
            messages.error(request, 'Accès refusé.')
            return redirect('sinistres_client:list')
        template = 'sinistres/rapport_indemnisation.html'
        back_url = 'sinistres_client:detail'
    else:
        template = 'sinistres/rapport_indemnisation.html'
        back_url = 'sinistres:detail'
    return render(request, template, {
        'rapport': rapport,
        'sinistre': sinistre,
        'back_url': back_url,
    })
