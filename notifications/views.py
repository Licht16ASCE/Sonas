from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import ActionEnAttente, Notification
from .services import get_content_object_url, mark_all_read, resolve_pending_action


def _notifications_list_route(user):
    return 'notifications_client:list' if user.is_client else 'notifications:list'


def _pending_actions_route(user):
    return 'notifications_client:pending_actions' if user.is_client else 'notifications:pending_actions'


def _mark_read_route(user, pk):
    if user.is_client:
        return 'notifications_client:mark_read', pk
    return 'notifications:mark_read', pk


def _open_route(user, pk):
    if user.is_client:
        return 'notifications_client:open', pk
    return 'notifications:open', pk


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(
        user=request.user,
    ).select_related('content_type').order_by('-created_at')[:50]
    return render(request, 'notifications/list.html', {'notifications': notifications})


@login_required
def notification_open(request, pk):
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    if not notif.is_read:
        notif.is_read = True
        notif.save(update_fields=['is_read'])
    target = get_content_object_url(request.user, notif.content_object)
    if target:
        return redirect(target)
    return redirect(_notifications_list_route(request.user))


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
        user=request.user, is_resolved=False,
    ).select_related('content_type').order_by('-created_at')
    return render(request, 'notifications/pending_actions.html', {'actions': actions})


@login_required
@require_POST
def pending_action_resolve(request, pk):
    resolve_pending_action(pk, request.user)
    return redirect(request.META.get('HTTP_REFERER') or _pending_actions_route(request.user))
