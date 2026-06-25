import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from contrats.models import Contrat


class SinistreStatut(models.TextChoices):
    DECLARE = 'DECLARE', 'Déclaré'
    EN_COURS = 'EN_COURS', 'En cours'
    VALIDE = 'VALIDE', 'Validé'
    REJETE = 'REJETE', 'Rejeté'


class SinistreType(models.TextChoices):
    DEGAT_EAUX = 'DEGAT_EAUX', 'Dégât des eaux'
    INCENDIE = 'INCENDIE', 'Incendie'
    VOL = 'VOL', 'Vol'
    TEMPETE = 'TEMPETE', 'Tempête'
    AUTRE = 'AUTRE', 'Autre'


class Sinistre(models.Model):
    """Sinistre lié à un contrat actif."""

    contrat = models.ForeignKey(Contrat, on_delete=models.CASCADE, related_name='sinistres')
    reference = models.CharField(max_length=50, unique=True)
    type_sinistre = models.CharField(max_length=20, choices=SinistreType.choices)
    description = models.TextField()
    date_sinistre = models.DateField()
    statut = models.CharField(max_length=15, choices=SinistreStatut.choices, default=SinistreStatut.DECLARE)
    motif_rejet = models.TextField(blank=True)
    montant_estime = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    declare_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sinistres_declares',
    )
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sinistres_valides',
    )
    date_validation = models.DateTimeField(null=True, blank=True)
    is_urgent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Sinistre'
        verbose_name_plural = 'Sinistres'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.reference} — {self.get_type_sinistre_display()}'

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f'SIN-{uuid.uuid4().hex[:8].upper()}'
        super().save(*args, **kwargs)

    def clean(self):
        if not self.contrat.can_declare_sinistre:
            raise ValidationError(
                'Impossible de déclarer un sinistre : contrat expiré ou sinistres bloqués.'
            )

    @property
    def client(self):
        return self.contrat.client

    @property
    def bien(self):
        return self.contrat.bien

    @property
    def has_required_documents(self):
        return self.documents.exists()
