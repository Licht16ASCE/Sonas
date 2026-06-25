from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'username', 'role', 'action', 'path', 'status_code')
    list_filter = ('role', 'status_code')
    search_fields = ('username', 'action', 'path', 'details')
    readonly_fields = (
        'user', 'username', 'role', 'action', 'method', 'path',
        'status_code', 'details', 'ip_address', 'created_at',
    )
