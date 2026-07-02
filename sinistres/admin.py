from django.contrib import admin

from .models import RapportIndemnisation, Sinistre


@admin.register(Sinistre)
class SinistreAdmin(admin.ModelAdmin):
    list_display = ('reference', 'contrat', 'type_sinistre', 'statut', 'montant_indemnise', 'is_urgent', 'created_at')
    list_filter = ('statut', 'type_sinistre', 'is_urgent')
    search_fields = ('reference', 'contrat__reference')


@admin.register(RapportIndemnisation)
class RapportIndemnisationAdmin(admin.ModelAdmin):
    list_display = ('reference', 'sinistre', 'montant_indemnise', 'depassement_detecte', 'contrat_invalide', 'created_at')
    search_fields = ('reference', 'sinistre__reference')
