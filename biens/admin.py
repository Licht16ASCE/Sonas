from django.contrib import admin

from .models import Bien


@admin.register(Bien)
class BienAdmin(admin.ModelAdmin):
    list_display = ('reference', 'client', 'type_bien', 'ville', 'statut', 'created_at')
    list_filter = ('statut', 'type_bien')
    search_fields = ('reference', 'adresse', 'ville', 'client__raison_sociale')
