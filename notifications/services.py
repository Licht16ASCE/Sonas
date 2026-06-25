"""
Services de notifications et actions en attente.
Regroupement intelligent pour éviter le spam.
"""
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from django.utils import timezone

from .models import ActionEnAttente, ActionType, Notification, NotificationPriority, NotificationType


def create_notification(user, notif_type, title, message, obj=None, priority='normal', digest_key=''):
    """Crée une notification, avec clé de digest pour regroupement."""
    ct = None
    object_id = None
    if obj is not None:
        ct = ContentType.objects.get_for_model(obj)
        object_id = obj.pk

    if not digest_key and obj is not None:
        digest_key = f'{notif_type}:{ct.id}:{object_id}'

    # Anti-spam : pas de doublon non lu identique dans les 24h
    from datetime import timedelta
    recent = Notification.objects.filter(
        user=user,
        digest_key=digest_key,
        is_read=False,
        created_at__gte=timezone.now() - timedelta(hours=24),
    )
    if digest_key and recent.exists():
        return recent.first()

    return Notification.objects.create(
        user=user,
        type_notification=notif_type,
        priority=priority,
        title=title,
        message=message,
        content_type=ct,
        object_id=object_id,
        digest_key=digest_key,
    )


def create_pending_action(user, action_type, title, description='', obj=None):
    """Crée une action en attente si elle n'existe pas déjà."""
    if obj is None:
        return None

    ct = ContentType.objects.get_for_model(obj)
    existing = ActionEnAttente.objects.filter(
        user=user,
        action_type=action_type,
        content_type=ct,
        object_id=obj.pk,
        is_resolved=False,
    )
    if existing.exists():
        return existing.first()

    return ActionEnAttente.objects.create(
        user=user,
        action_type=action_type,
        title=title,
        description=description,
        content_type=ct,
        object_id=obj.pk,
    )


def resolve_pending_for_object(obj, action_type=None):
    """Marque les actions en attente comme résolues pour un objet."""
    ct = ContentType.objects.get_for_model(obj)
    qs = ActionEnAttente.objects.filter(
        content_type=ct,
        object_id=obj.pk,
        is_resolved=False,
    )
    if action_type:
        qs = qs.filter(action_type=action_type)

    qs.update(is_resolved=True, resolved_at=timezone.now())


def get_pending_actions_count(user):
    return ActionEnAttente.objects.filter(user=user, is_resolved=False).count()


def get_unread_count(user):
    return Notification.objects.filter(user=user, is_read=False).count()


def get_recent_notifications(user, limit=5):
    return Notification.objects.filter(user=user).order_by('-created_at')[:limit]


def get_grouped_notifications_summary(user):
    """Résumé regroupé pour le dashboard."""
    unread = Notification.objects.filter(user=user, is_read=False)
    grouped = unread.values('type_notification').annotate(count=Count('id'))
    return list(grouped)


def mark_all_read(user):
    Notification.objects.filter(user=user, is_read=False).update(is_read=True)
