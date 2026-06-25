from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .models import ActionEnAttente, Notification
from .services import mark_all_read


def _notifications_list_route(user):
    return 'notifications_client:list' if user.is_client else 'notifications:list'


def _pending_actions_route(user):
    return 'notifications_client:pending_actions' if user.is_client else 'notifications:pending_actions'


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:50]
    return render(request, 'notifications/list.html', {'notifications': notifications})


@login_required
@require_POST
def notification_mark_read(request, pk):
    notif = Notification.objects.filter(pk=pk, user=request.user).first()
    if notif:
        notif.is_read = True
        notif.save(update_fields=['is_read'])
    return redirect(request.META.get('HTTP_REFERER') or _notifications_list_route(request.user))


@login_required
@require_POST
def notification_mark_all_read(request):
    mark_all_read(request.user)
    return redirect(_notifications_list_route(request.user))


@login_required
def pending_actions_list(request):
    actions = ActionEnAttente.objects.filter(
        user=request.user, is_resolved=False
    ).select_related('content_type')
    return render(request, 'notifications/pending_actions.html', {'actions': actions})
