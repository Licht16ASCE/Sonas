from django.contrib import admin

from .models import ActiviteClient, Client


class ActiviteClientInline(admin.TabularInline):
    model = ActiviteClient
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'email', 'ville', 'is_active', 'created_at')
    list_filter = ('is_active', 'ville')
    search_fields = ('raison_sociale', 'user__username', 'user__email', 'user__first_name', 'user__last_name')
    inlines = [ActiviteClientInline]


@admin.register(ActiviteClient)
class ActiviteClientAdmin(admin.ModelAdmin):
    list_display = ('client', 'type_activite', 'created_at')
    list_filter = ('type_activite',)
