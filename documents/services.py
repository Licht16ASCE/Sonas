"""Requêtes et filtres pour la liste documentaire interne."""

from django.db.models import Q

from clients.models import Client
from .models import Document, DocumentType


def get_internal_documents_queryset():
    return Document.objects.select_related(
        'sinistre',
        'sinistre__contrat',
        'sinistre__contrat__client',
        'sinistre__contrat__client__user',
        'bien',
        'bien__client',
        'bien__client__user',
        'contrat',
        'contrat__client',
        'contrat__client__user',
        'uploaded_by',
    )


def filter_internal_documents(queryset, *, client_id=None, type_document=None, search=''):
    if client_id:
        queryset = queryset.filter(
            Q(sinistre__contrat__client_id=client_id)
            | Q(bien__client_id=client_id)
            | Q(contrat__client_id=client_id)
        )

    if type_document and type_document in dict(DocumentType.choices):
        queryset = queryset.filter(type_document=type_document)

    search = (search or '').strip()
    if search:
        queryset = queryset.filter(
            Q(titre__icontains=search)
            | Q(sinistre__reference__icontains=search)
            | Q(bien__reference__icontains=search)
            | Q(contrat__reference__icontains=search)
            | Q(bien__client__raison_sociale__icontains=search)
            | Q(bien__client__user__first_name__icontains=search)
            | Q(bien__client__user__last_name__icontains=search)
            | Q(bien__client__user__username__icontains=search)
            | Q(sinistre__contrat__client__raison_sociale__icontains=search)
            | Q(sinistre__contrat__client__user__first_name__icontains=search)
            | Q(sinistre__contrat__client__user__last_name__icontains=search)
            | Q(contrat__client__raison_sociale__icontains=search)
            | Q(contrat__client__user__first_name__icontains=search)
            | Q(contrat__client__user__last_name__icontains=search)
        ).distinct()

    return queryset


def get_document_filter_clients():
    return Client.objects.filter(is_active=True).select_related('user').order_by(
        'raison_sociale', 'user__last_name', 'user__first_name',
    )
