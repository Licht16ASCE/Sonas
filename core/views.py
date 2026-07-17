from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from core.decorators import admin_required, internal_required


def landing(request):
    """Page d'accueil publique."""
    return render(request, 'core/landing.html')


@require_GET
def geo_adresse_search(request):
    """Suggestions d'adresses OpenStreetMap limitées à une ville RDC."""
    ville = (request.GET.get('ville') or '').strip()
    query = (request.GET.get('q') or '').strip()
    if not ville:
        return JsonResponse({'results': [], 'error': 'Sélectionnez d\'abord une ville.'}, status=400)
    if len(query) < 3:
        return JsonResponse({'results': [], 'ville': ville})

    from core.geocode_rdc import search_adresses_rdc

    results, api_ok = search_adresses_rdc(ville, query, limit=6)
    payload = {'results': results, 'ville': ville, 'api_ok': api_ok}
    if not api_ok:
        payload['error'] = 'Service cartographique temporairement indisponible.'
    return JsonResponse(payload)


@require_GET
def geo_adresse_verify(request):
    """Vérifie qu'une adresse est localisable en RDC pour la ville donnée."""
    ville = (request.GET.get('ville') or '').strip()
    adresse = (request.GET.get('adresse') or '').strip()
    from core.geocode_rdc import verify_adresse_rdc

    ok, detail, error = verify_adresse_rdc(adresse, ville)
    return JsonResponse({'ok': ok, 'result': detail, 'error': error, 'ville': ville})


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
