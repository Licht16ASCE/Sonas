"""
Services de notifications et actions en attente.
Regroupement intelligent pour éviter le spam.
"""
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, UserRole
from .models import ActionEnAttente, ActionType, Notification, NotificationPriority, NotificationType

STAFF_ROLES_AGENTS = (UserRole.AGENT,)
STAFF_ROLES_GERANTS = (UserRole.GERANT, UserRole.ADMIN)
STAFF_ROLES_ALL = (UserRole.AGENT, UserRole.GERANT, UserRole.ADMIN)

_OBJECT_ROUTES = {
    'bien': ('biens_client:detail', 'biens:detail'),
    'contrat': ('contrats_client:detail', 'contrats:detail'),
    'sinistre': ('sinistres_client:detail', 'sinistres:detail'),
}


def get_staff_users(roles=STAFF_ROLES_ALL):
    return User.objects.filter(role__in=roles, is_active=True)


def get_content_object_url(user, obj):
    if obj is None:
        return ''
    model = obj._meta.model_name
    routes = _OBJECT_ROUTES.get(model)
    if not routes:
        return ''
    client_route, internal_route = routes
    route_name = client_route if user.is_client else internal_route
    return reverse(route_name, args=[obj.pk])


def notify_staff(
    *,
    roles=STAFF_ROLES_ALL,
    notif_type=NotificationType.ACTION_PENDING,
    title,
    message,
    obj=None,
    priority='normal',
    pending_action_type=None,
    pending_title='',
    pending_description='',
    exclude_user=None,
):
    """Crée notifications et actions en attente pour le personnel interne."""
    for user in get_staff_users(roles):
        if exclude_user and user.pk == exclude_user.pk:
            continue
        create_notification(
            user,
            notif_type,
            title,
            message,
            obj=obj,
            priority=priority,
        )
        if pending_action_type and pending_title and obj is not None:
            create_pending_action(
                user,
                pending_action_type,
                pending_title,
                pending_description,
                obj=obj,
            )


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
    labels = dict(NotificationType.choices)
    return [
        {
            'type_notification': row['type_notification'],
            'type_label': labels.get(row['type_notification'], row['type_notification']),
            'count': row['count'],
        }
        for row in grouped
    ]


def resolve_pending_action(pk, user):
    """Marque une action en attente comme résolue pour l'utilisateur."""
    updated = ActionEnAttente.objects.filter(
        pk=pk,
        user=user,
        is_resolved=False,
    ).update(is_resolved=True, resolved_at=timezone.now())
    return updated > 0


def mark_all_read(user):
    Notification.objects.filter(user=user, is_read=False).update(is_read=True)
