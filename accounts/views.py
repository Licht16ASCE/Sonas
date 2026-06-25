from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from clients.forms import ClientRegisterForm
from clients.models import ActiviteClient
from clients.services import log_client_activity
from .forms import LoginForm


@require_http_methods(['GET', 'POST'])
def login_view(request):
    if request.user.is_authenticated:
        return redirect(request.user.get_dashboard_url())

    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        next_url = request.GET.get('next')
        if next_url:
            return redirect(next_url)
        return redirect(user.get_dashboard_url())

    return render(request, 'accounts/login.html', {'form': form})


@require_http_methods(['GET', 'POST'])
def register_view(request):
    if request.user.is_authenticated:
        return redirect(request.user.get_dashboard_url())

    form = ClientRegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        log_client_activity(
            user.client_profile,
            ActiviteClient.TypeActivite.AUTRE,
            'Compte créé via inscription en ligne',
            user,
        )
        messages.success(request, 'Bienvenue ! Votre compte client a été créé.')
        return redirect(user.get_dashboard_url())

    return render(request, 'accounts/register.html', {'form': form})


@require_POST
@login_required
def logout_view(request):
    logout(request)
    return redirect('core:landing')


@login_required
@require_POST
def update_theme(request):
    theme = request.POST.get('theme', 'system')
    if theme in ('light', 'dark', 'system'):
        request.user.theme_preference = theme
        request.user.save(update_fields=['theme_preference'])
    return redirect(request.META.get('HTTP_REFERER', '/'))


@login_required
def settings_view(request):
    from accounts.models import User

    if request.method == 'POST':
        theme = request.POST.get('theme', 'system')
        if theme in ('light', 'dark', 'system'):
            request.user.theme_preference = theme
            request.user.save(update_fields=['theme_preference'])
        return redirect('accounts:settings')

    theme_choices = User._meta.get_field('theme_preference').choices
    return render(request, 'accounts/settings.html', {'theme_choices': theme_choices})
