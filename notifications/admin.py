from django.contrib import admin

from .models import ActionEnAttente, Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'type_notification', 'priority', 'is_read', 'created_at')
    list_filter = ('type_notification', 'priority', 'is_read')


@admin.register(ActionEnAttente)
class ActionEnAttenteAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'action_type', 'is_resolved', 'created_at')
    list_filter = ('action_type', 'is_resolved')
