from django.contrib import admin

from .models import Sinistre


@admin.register(Sinistre)
class SinistreAdmin(admin.ModelAdmin):
    list_display = ('reference', 'contrat', 'type_sinistre', 'statut', 'is_urgent', 'created_at')
    list_filter = ('statut', 'type_sinistre', 'is_urgent')
    search_fields = ('reference', 'contrat__reference')
