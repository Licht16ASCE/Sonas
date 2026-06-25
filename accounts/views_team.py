from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.forms import AgentCreateForm
from accounts.models import UserRole
from core.audit import log_audit_action
from core.decorators import gerant_required

User = get_user_model()


@gerant_required
def agent_list(request):
    agents = User.objects.filter(role=UserRole.AGENT).order_by('-date_joined')
    return render(request, 'accounts/agent_list.html', {'agents': agents})


@gerant_required
def agent_create(request):
    if request.method == 'POST':
        form = AgentCreateForm(request.POST)
        if form.is_valid():
            agent = form.save()
            log_audit_action(
                request,
                action='AGENT_CREE',
                details=f'Agent {agent.username} créé par {request.user.username}',
            )
            messages.success(request, f'Agent {agent.get_full_name() or agent.username} créé.')
            return redirect('accounts_team:list')
    else:
        form = AgentCreateForm()
    return render(request, 'accounts/agent_form.html', {'form': form, 'title': 'Nouvel agent'})


@gerant_required
@require_POST
def agent_toggle_active(request, pk):
    agent = get_object_or_404(User, pk=pk, role=UserRole.AGENT)
    agent.is_active = not agent.is_active
    agent.save(update_fields=['is_active'])
    state = 'activé' if agent.is_active else 'désactivé'
    log_audit_action(
        request,
        action='AGENT_DESACTIVE' if not agent.is_active else 'AGENT_ACTIVE',
        details=f'Agent {agent.username} {state} par {request.user.username}',
    )
    messages.success(request, f'Agent {agent.username} {state}.')
    return redirect('accounts_team:list')
