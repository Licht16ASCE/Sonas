"""
Tâches Celery — digest quotidien regroupé.
"""
from celery import shared_task
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone

from .models import NotificationType
from .services import create_notification


@shared_task
def send_daily_digest():
    """Digest quotidien regroupé — une notification résumé par utilisateur."""
    User = get_user_model()
    users_with_unread = User.objects.filter(
        notifications__is_read=False
    ).annotate(unread_count=Count('notifications')).filter(unread_count__gt=0).distinct()

    sent = 0
    for user in users_with_unread:
        unread_count = user.notifications.filter(is_read=False).count()
        pending_types = (
            user.notifications.filter(is_read=False)
            .values('type_notification')
            .annotate(c=Count('id'))
        )
        summary_parts = []
        type_labels = dict(NotificationType.choices)
        for item in pending_types:
            label = type_labels.get(item['type_notification'], item['type_notification'])
            summary_parts.append(f'{label}: {item["c"]}')

        create_notification(
            user=user,
            notif_type=NotificationType.DIGEST,
            title=f'Résumé du jour — {unread_count} notification(s)',
            message=' | '.join(summary_parts) or 'Consultez votre tableau de bord.',
            digest_key=f'digest:{user.pk}:{timezone.now().date()}',
            priority='low',
        )
        sent += 1

    return f'Digest sent to {sent} users'
