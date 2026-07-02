import logging

from .models import AuditLog

file_logger = logging.getLogger('sonas.critical')


def log_audit_action(request, action, details='', status_code=200):
    """Enregistre une action interne en base et dans le fichier log."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return

    username = user.username
    role = getattr(user, 'role', '')
    ip = request.META.get('REMOTE_ADDR')

    AuditLog.objects.create(
        user=user,
        username=username,
        role=role,
        action=action[:120],
        method=request.method,
        path=request.path[:500],
        status_code=status_code,
        details=details[:2000],
        ip_address=ip,
    )
    file_logger.info(
        'AUDIT | user=%s | role=%s | action=%s | path=%s | status=%s | %s',
        username, role, action, request.path, status_code, details,
    )
