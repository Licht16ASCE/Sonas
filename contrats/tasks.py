"""
Tâches Celery pour la gestion des expirations de contrats.
J-30 : notification simple
J-15 : rappel
J-7  : alerte
J0   : expiration
Post : blocage sinistres
"""
from celery import shared_task
from django.utils import timezone

from notifications.services import create_notification, create_pending_action


@shared_task
def check_contract_expirations():
    from contrats.models import Contrat, ContratStatut

    contrats = Contrat.objects.filter(statut=ContratStatut.ACTIF).select_related(
        'client', 'client__user'
    )
    processed = 0

    for contrat in contrats:
        phase = contrat.get_expiration_phase()
        if not phase:
            continue

        user = contrat.client.user
        jours = contrat.jours_restants

        if phase == 'J30' and not contrat.alerte_j30_envoyee:
            create_notification(
                user=user,
                notif_type='CONTRAT_EXPIRATION',
                title=f'Contrat {contrat.reference} — expiration dans 30 jours',
                message=f'Votre contrat expire le {contrat.date_fin}.',
                obj=contrat,
                priority='normal',
            )
            contrat.alerte_j30_envoyee = True
            contrat.save(update_fields=['alerte_j30_envoyee'])

        elif phase == 'J15' and not contrat.alerte_j15_envoyee:
            create_notification(
                user=user,
                notif_type='CONTRAT_EXPIRATION',
                title=f'Rappel — contrat {contrat.reference} expire dans 15 jours',
                message='Pensez à renouveler votre contrat.',
                obj=contrat,
                priority='normal',
            )
            contrat.alerte_j15_envoyee = True
            contrat.save(update_fields=['alerte_j15_envoyee'])

        elif phase == 'J7' and not contrat.alerte_j7_envoyee:
            create_notification(
                user=user,
                notif_type='CONTRAT_EXPIRATION',
                title=f'Alerte — contrat {contrat.reference} expire dans 7 jours',
                message='Action requise : renouvellement imminent.',
                obj=contrat,
                priority='high',
            )
            create_pending_action(
                user=user,
                action_type='CONTRAT_EXPIRATION',
                title=f'Renouveler le contrat {contrat.reference}',
                description=f'Expiration dans {jours} jours.',
                obj=contrat,
            )
            contrat.alerte_j7_envoyee = True
            contrat.save(update_fields=['alerte_j7_envoyee'])

        elif phase == 'J0' and not contrat.alerte_j0_envoyee:
            create_notification(
                user=user,
                notif_type='CONTRAT_EXPIRATION',
                title=f'Contrat {contrat.reference} expire aujourd\'hui',
                message='Votre contrat expire aujourd\'hui.',
                obj=contrat,
                priority='critical',
            )
            contrat.alerte_j0_envoyee = True
            contrat.save(update_fields=['alerte_j0_envoyee'])

        elif phase == 'POST':
            if contrat.check_and_update_expiration():
                create_notification(
                    user=user,
                    notif_type='CONTRAT_EXPIRATION',
                    title=f'Contrat {contrat.reference} expiré',
                    message='Les déclarations de sinistre sont bloquées.',
                    obj=contrat,
                    priority='critical',
                )

        processed += 1

    return f'Processed {processed} contracts at {timezone.now()}'
