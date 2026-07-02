from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from accounts.models import UserRole


def role_required(*roles):
    """Décorateur : accès limité aux rôles spécifiés."""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                if request.user.is_client:
                    return redirect('/client/')
                return HttpResponseForbidden('Accès non autorisé.')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def internal_required(view_func):
    """Accès réservé aux utilisateurs internes (agent, gérant, admin)."""
    return role_required(
        UserRole.AGENT, UserRole.GERANT, UserRole.ADMIN
    )(view_func)


def gerant_required(view_func):
    """Accès réservé au gérant."""
    return role_required(UserRole.GERANT)(view_func)


def gerant_or_admin_required(view_func):
    """Validation métier — gérant ou admin uniquement."""
    return role_required(UserRole.GERANT, UserRole.ADMIN)(view_func)


def admin_required(view_func):
    return role_required(UserRole.ADMIN)(view_func)


def client_required(view_func):
    return role_required(UserRole.CLIENT)(view_func)
