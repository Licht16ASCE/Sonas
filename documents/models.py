import os
import uuid

from django.conf import settings
from django.db import models

from biens.models import Bien
from sinistres.models import Sinistre


def document_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    folder = 'misc'
    if instance.contrat_id:
        folder = f'contrats/{instance.contrat_id}'
    elif instance.sinistre_id:
        folder = f'sinistres/{instance.sinistre_id}'
    elif instance.bien_id:
        folder = f'biens/{instance.bien_id}'
    return f'documents/{folder}/{uuid.uuid4().hex}{ext}'


class DocumentType(models.TextChoices):
    JUSTIFICATIF = 'JUSTIFICATIF', 'Justificatif'
    PHOTO = 'PHOTO', 'Photo'
    RAPPORT = 'RAPPORT', 'Rapport'
    CONTRAT_PDF = 'CONTRAT_PDF', 'Contrat PDF'
    BON_PAIEMENT = 'BON_PAIEMENT', 'Bon de paiement'
    PREUVE_PAIEMENT = 'PREUVE_PAIEMENT', 'Preuve de paiement'
    RETRAIT_BANCAIRE = 'RETRAIT_BANCAIRE', 'Retrait bancaire'
    AUTRE = 'AUTRE', 'Autre'


class Document(models.Model):
    """Document lié à un sinistre et/ou un bien."""

    sinistre = models.ForeignKey(
        Sinistre, on_delete=models.CASCADE, null=True, blank=True, related_name='documents'
    )
    bien = models.ForeignKey(
        Bien, on_delete=models.CASCADE, null=True, blank=True, related_name='documents'
    )
    contrat = models.ForeignKey(
        'contrats.Contrat',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='documents',
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
        links = sum(bool(x) for x in (self.sinistre, self.bien, self.contrat))
        if links == 0:
            raise ValidationError('Un document doit être lié à un sinistre, un bien ou un contrat.')
        if links > 1:
            raise ValidationError('Un document ne peut être lié qu\'à une seule entité.')

    @property
    def linked_entity_type(self):
        if self.contrat_id:
            return 'contrat'
        if self.sinistre_id:
            return 'sinistre'
        if self.bien_id:
            return 'bien'
        return None

    @property
    def client(self):
        if self.contrat_id:
            return self.contrat.client
        if self.sinistre_id:
            return self.sinistre.client
        if self.bien_id:
            return self.bien.client
        return None

    @property
    def linked_reference(self):
        if self.contrat_id:
            return self.contrat.reference
        if self.sinistre_id:
            return self.sinistre.reference
        if self.bien_id:
            return self.bien.reference
        return None
