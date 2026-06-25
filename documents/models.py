import os
import uuid

from django.conf import settings
from django.db import models

from biens.models import Bien
from sinistres.models import Sinistre


def document_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    folder = 'misc'
    if instance.sinistre_id:
        folder = f'sinistres/{instance.sinistre_id}'
    elif instance.bien_id:
        folder = f'biens/{instance.bien_id}'
    return f'documents/{folder}/{uuid.uuid4().hex}{ext}'


class DocumentType(models.TextChoices):
    JUSTIFICATIF = 'JUSTIFICATIF', 'Justificatif'
    PHOTO = 'PHOTO', 'Photo'
    RAPPORT = 'RAPPORT', 'Rapport'
    CONTRAT_PDF = 'CONTRAT_PDF', 'Contrat PDF'
    AUTRE = 'AUTRE', 'Autre'


class Document(models.Model):
    """Document lié à un sinistre et/ou un bien."""

    sinistre = models.ForeignKey(
        Sinistre, on_delete=models.CASCADE, null=True, blank=True, related_name='documents'
    )
    bien = models.ForeignKey(
        Bien, on_delete=models.CASCADE, null=True, blank=True, related_name='documents'
    )
    type_document = models.CharField(max_length=20, choices=DocumentType.choices, default=DocumentType.JUSTIFICATIF)
    titre = models.CharField(max_length=200)
    fichier = models.FileField(upload_to=document_upload_path)
    taille_octets = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='documents_uploades',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'
        ordering = ['-created_at']

    def __str__(self):
        return self.titre

    def save(self, *args, **kwargs):
        if self.fichier and not self.taille_octets:
            self.taille_octets = self.fichier.size
        super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.sinistre and not self.bien:
            raise ValidationError('Un document doit être lié à un sinistre ou un bien.')

    @property
    def linked_entity_type(self):
        if self.sinistre_id:
            return 'sinistre'
        return 'bien'
