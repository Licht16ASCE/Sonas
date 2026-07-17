from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from clients.forms import ClientRegisterForm
from clients.models import ActiviteClient
from clients.services import log_client_activity
from .forms import LoginForm, SonasPasswordChangeForm, UserAccountForm


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
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('accounts:settings')


def _settings_redirect(section):
    url = reverse('accounts:settings')
    if section:
        return redirect(f'{url}?section={section}')
    return redirect(url)


@login_required
def settings_view(request):
    from accounts.models import User

    user = request.user
    active_section = request.GET.get('section', 'account')
    if active_section not in ('account', 'security', 'appearance', 'session'):
        active_section = 'account'

    account_form = UserAccountForm(instance=user)
    password_form = SonasPasswordChangeForm(user)

    if request.method == 'POST':
        section = request.POST.get('section')

        if section == 'account':
            account_form = UserAccountForm(request.POST, instance=user)
            if account_form.is_valid():
                account_form.save()
                if user.is_client and hasattr(user, 'client_profile'):
                    log_client_activity(
                        user.client_profile,
                        ActiviteClient.TypeActivite.PROFIL_MODIFIE,
                        'Informations de compte mises à jour',
                        user,
                    )
                messages.success(request, 'Informations de compte enregistrées.')
                return _settings_redirect('account')
            active_section = 'account'

        elif section == 'security':
            password_form = SonasPasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                messages.success(request, 'Mot de passe modifié avec succès.')
                return _settings_redirect('security')
            active_section = 'security'

        elif section == 'appearance':
            theme = request.POST.get('theme', 'system')
            if theme in ('light', 'dark', 'system'):
                user.theme_preference = theme
                user.save(update_fields=['theme_preference'])
                messages.success(request, 'Préférence d\'affichage enregistrée.')
                return _settings_redirect('appearance')
            active_section = 'appearance'
 
    theme_choices = User._meta.get_field('theme_preference').choices
    return render(request, 'accounts/settings.html', {
        'account_form': account_form,
        'password_form': password_form,
        'theme_choices': theme_choices,
        'active_section': active_section,
    })
