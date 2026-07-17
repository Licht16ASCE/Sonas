from django.contrib import admin

from .models import Contrat, GrilleTarifaire, PoliceAssurance, PreuvePaiement


@admin.register(GrilleTarifaire)
class GrilleTarifaireAdmin(admin.ModelAdmin):
    list_display = ('libelle', 'type_bien', 'valeur_min', 'valeur_max', 'prime_annuelle', 'plafond_indemnisation', 'is_active')
    list_filter = ('type_bien', 'is_active')


@admin.register(Contrat)
class ContratAdmin(admin.ModelAdmin):
    list_display = ('reference', 'client', 'bien', 'statut', 'paiement_valide', 'date_debut', 'date_fin')
    list_filter = ('statut', 'paiement_valide')
    search_fields = ('reference', 'client__raison_sociale', 'bon_paiement_reference')


@admin.register(PoliceAssurance)
class PoliceAssuranceAdmin(admin.ModelAdmin):
    list_display = ('reference', 'client', 'bien', 'type_assurance', 'prime_annuelle', 'created_at')
    search_fields = ('reference',)


@admin.register(PreuvePaiement)
class PreuvePaiementAdmin(admin.ModelAdmin):
    list_display = ('reference', 'contrat', 'client', 'is_validated', 'created_at')
    list_filter = ('is_validated',)
