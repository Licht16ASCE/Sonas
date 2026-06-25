import logging
from datetime import datetime, timezone

from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import resolve, reverse
from django.utils.deprecation import MiddlewareMixin

from accounts.models import UserRole

logger = logging.getLogger('sonas.critical')

# Routes publiques sans authentification
PUBLIC_PREFIXES = ('/', '/accounts/login', '/static/', '/media/')
PUBLIC_NAMES = ('core:landing', 'accounts:login')


class SessionTimeoutMiddleware(MiddlewareMixin):
    """Déconnexion automatique après 20 minutes d'inactivité."""

    def process_request(self, request):
        if not request.user.is_authenticated:
            return None

        now = datetime.now(timezone.utc).timestamp()
        last_activity = request.session.get('last_activity')

        if last_activity and (now - last_activity) > settings.SESSION_COOKIE_AGE:
            logout(request)
            return redirect(f"{reverse('accounts:login')}?timeout=1")

        request.session['last_activity'] = now
        return None


class RoleProtectionMiddleware(MiddlewareMixin):
    """Séparation stricte des espaces client / interne / admin."""

    def process_request(self, request):
        path = request.path

        if path.startswith('/static/') or path.startswith('/media/'):
            return None

        if path == '/' or path.startswith('/accounts/login'):
            return None

        if not request.user.is_authenticated:
            if path.startswith('/client/') or path.startswith('/sonas/'):
                return redirect(f"{reverse('accounts:login')}?next={path}")
            return None

        user = request.user

        # Espace client — réservé aux CLIENT
        if path.startswith('/client/'):
            if not user.is_client:
                return redirect(user.get_dashboard_url())

        # Espace interne — AGENT, GERANT, ADMIN
        elif path.startswith('/sonas/') and not path.startswith(f'/{settings.ADMIN_URL}'):
            if user.is_client:
                return redirect('/client/')

        return None


class InternalActionLogMiddleware(MiddlewareMixin):
    """Journalise les POST des agents et gérants sur l'espace interne."""

    SKIP_PREFIXES = ('/sonas/notifications/',)

    def process_response(self, request, response):
        if request.method != 'POST':
            return response

        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return response
        if user.role not in (UserRole.AGENT, UserRole.GERANT):
            return response

        path = request.path
        if not path.startswith('/sonas/') or any(path.startswith(p) for p in self.SKIP_PREFIXES):
            return response

        from core.audit import log_audit_action

        match = getattr(request, 'resolver_match', None)
        action_label = request.POST.get('action') or (match.url_name if match else 'POST')
        details_parts = []
        for key in ('statut', 'motif_rejet', 'username'):
            if key in request.POST:
                details_parts.append(f'{key}={request.POST.get(key)}')
        log_audit_action(
            request,
            action=str(action_label)[:120],
            details=' | '.join(details_parts) or f'POST {path}',
            status_code=response.status_code,
        )
        return response


class CriticalActionLogMiddleware(MiddlewareMixin):
    """Journalisation des actions critiques (POST sur entités sensibles)."""

    CRITICAL_PREFIXES = (
        '/sonas/sinistres/',
        '/sonas/contrats/',
        '/sonas/clients/',
    )

    def process_response(self, request, response):
        if request.method != 'POST':
            return response

        path = request.path
        if any(path.startswith(p) for p in self.CRITICAL_PREFIXES):
            user = getattr(request, 'user', None)
            username = user.username if user and user.is_authenticated else 'anonymous'
            logger.info(
                'CRITICAL ACTION | user=%s | path=%s | status=%s',
                username, path, response.status_code,
            )
        return response
