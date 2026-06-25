def global_context(request):
    """Contexte global pour templates (notifications, actions en attente, thème)."""
    from django.conf import settings

    ctx = {
        'theme_preference': 'system',
        'pending_actions_count': 0,
        'unread_notifications_count': 0,
        'recent_notifications': [],
        'pending_decisions_count': 0,
        'urgent_sinistres_count': 0,
        'admin_url': settings.ADMIN_URL,
    }

    if not request.user.is_authenticated:
        return ctx

    ctx['theme_preference'] = request.user.theme_preference

    from notifications.services import (
        get_pending_actions_count,
        get_recent_notifications,
        get_unread_count,
    )

    ctx['pending_actions_count'] = get_pending_actions_count(request.user)
    ctx['unread_notifications_count'] = get_unread_count(request.user)
    ctx['recent_notifications'] = get_recent_notifications(request.user, limit=5)

    if request.user.is_client:
        ctx['url_notifications_list'] = 'notifications_client:list'
        ctx['url_pending_actions'] = 'notifications_client:pending_actions'
    else:
        ctx['url_notifications_list'] = 'notifications:list'
        ctx['url_pending_actions'] = 'notifications:pending_actions'

    if request.user.is_internal:
        from sinistres.models import Sinistre, SinistreStatut

        ctx['pending_decisions_count'] = Sinistre.objects.filter(
            statut=SinistreStatut.EN_COURS
        ).count()
        ctx['urgent_sinistres_count'] = Sinistre.objects.filter(
            is_urgent=True,
            statut__in=(SinistreStatut.DECLARE, SinistreStatut.EN_COURS),
        ).count()

    return ctx
