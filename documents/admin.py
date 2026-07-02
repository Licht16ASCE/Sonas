from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('titre', 'type_document', 'sinistre', 'bien', 'created_at')
    list_filter = ('type_document',)
