from django.contrib import admin

from .models import Contrat


@admin.register(Contrat)
class ContratAdmin(admin.ModelAdmin):
    list_display = ('reference', 'client', 'bien', 'statut', 'date_debut', 'date_fin')
    list_filter = ('statut',)
    search_fields = ('reference', 'client__raison_sociale')
