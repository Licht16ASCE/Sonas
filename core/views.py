from django.conf import settings
from django.shortcuts import render

from core.decorators import admin_required, internal_required


def landing(request):
    """Page d'accueil publique."""
    return render(request, 'core/landing.html')


@internal_required
def dashboard_internal(request):
    """Dashboard principal espace interne."""
    from biens.models import Bien
    from clients.models import Client
    from contrats.models import Contrat
    from sinistres.models import Sinistre
    from notifications.models import ActionEnAttente

    filter_key = request.GET.get('filter', 'all')

    sinistres_qs = Sinistre.objects.select_related('contrat', 'contrat__bien', 'contrat__client')
    biens_qs = Bien.objects.select_related('client')
    contrats_qs = Contrat.objects.select_related('client', 'bien')

    kpis = {
        'clients': Client.objects.filter(is_active=True).count(),
        'biens': biens_qs.count(),
        'contrats_actifs': contrats_qs.filter(statut='ACTIF').count(),
        'sinistres_en_cours': sinistres_qs.filter(statut='EN_COURS').count(),
    }

    pending_actions = ActionEnAttente.objects.filter(
        user=request.user, is_resolved=False
    ).select_related('content_type')[:10]

    from core.filters import FILTER_CHOICES
    from notifications.services import get_grouped_notifications_summary

    return render(request, 'core/dashboard_internal.html', {
        'kpis': kpis,
        'pending_actions': pending_actions,
        'notifications_summary': get_grouped_notifications_summary(request.user),
        'filter_choices': FILTER_CHOICES,
        'active_filter': filter_key,
        'recent_sinistres': sinistres_qs.order_by('-created_at')[:5],
    })


@admin_required
def admin_system(request):
    """Vue technique — état du système."""
    from django.db import connection

    db_engine = connection.settings_dict.get('ENGINE', '').split('.')[-1]
    return render(request, 'core/admin_system.html', {
        'db_engine': db_engine,
        'debug_mode': settings.DEBUG,
        'admin_url': settings.ADMIN_URL,
        'session_timeout_min': settings.SESSION_COOKIE_AGE // 60,
    })


@admin_required
def admin_logs(request):
    """Consultation des logs d'audit internes."""
    from core.models import AuditLog

    audit_logs = AuditLog.objects.select_related('user').all()[:200]
    log_path = settings.BASE_DIR / 'logs' / 'sonas.log'
    file_lines = []
    if log_path.exists():
        with open(log_path, encoding='utf-8', errors='replace') as f:
            file_lines = list(reversed(f.readlines()[-50:]))
    return render(request, 'core/admin_logs.html', {
        'audit_logs': audit_logs,
        'file_lines': file_lines,
    })
