from django.db.models import Q


# Filtres UX réutilisables sur les listes internes
FILTER_CHOICES = [
    ('all', 'Tous'),
    ('en_attente', 'En attente'),
    ('en_cours', 'En cours'),
    ('valides', 'Validés'),
    ('rejetes', 'Rejetés'),
    ('urgents', 'Urgents'),
    ('docs_manquants', 'Documents manquants'),
]


def apply_status_filter(queryset, status_field, filter_key):
    """Applique un filtre de statut standard sur un queryset."""
    mapping = {
        'en_attente': {status_field: 'EN_ATTENTE'},
        'en_cours': {status_field: 'EN_COURS'},
        'valides': {status_field: 'VALIDE'},
        'rejetes': {status_field: 'REJETE'},
    }
    if filter_key in mapping:
        return queryset.filter(**mapping[filter_key])
    return queryset


def get_active_filter(request, default='all'):
    return request.GET.get('filter', default)
