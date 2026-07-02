from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'role', 'first_name', 'last_name', 'is_active')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('SONAS', {'fields': ('role', 'phone', 'theme_preference')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('SONAS', {'fields': ('role', 'phone')}),
    )
