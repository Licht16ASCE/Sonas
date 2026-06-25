import uuid
from datetime import date, timedelta

from django.db import models

from biens.models import Bien
from clients.models import Client


class ContratStatut(models.TextChoices):
    BROUILLON = 'BROUILLON', 'Brouillon'
    ACTIF = 'ACTIF', 'Actif'
    EXPIRE = 'EXPIRE', 'Expiré'
    RESILIE = 'RESILIE', 'Résilié'


class Contrat(models.Model):
    """Contrat liant un client à un bien."""

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='contrats')
    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name='contrats')
    reference = models.CharField(max_length=50, unique=True)
    date_debut = models.DateField()
    date_fin = models.DateField()
    statut = models.CharField(max_length=15, choices=ContratStatut.choices, default=ContratStatut.BROUILLON)
    montant_annuel = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    # Suivi expiration
    alerte_j30_envoyee = models.BooleanField(default=False)
    alerte_j15_envoyee = models.BooleanField(default=False)
    alerte_j7_envoyee = models.BooleanField(default=False)
    alerte_j0_envoyee = models.BooleanField(default=False)
    sinistres_bloques = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Contrat'
        verbose_name_plural = 'Contrats'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.reference} — {self.client}'

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f'CTR-{uuid.uuid4().hex[:8].upper()}'
        super().save(*args, **kwargs)

    @property
    def jours_restants(self):
        return (self.date_fin - date.today()).days

    @property
    def is_expired(self):
        return self.date_fin < date.today() or self.statut == ContratStatut.EXPIRE

    @property
    def can_declare_sinistre(self):
        return self.statut == ContratStatut.ACTIF and not self.sinistres_bloques

    def check_and_update_expiration(self):
        """Met à jour le statut et bloque les sinistres post-expiration."""
        today = date.today()
        if self.date_fin < today and self.statut == ContratStatut.ACTIF:
            self.statut = ContratStatut.EXPIRE
            self.sinistres_bloques = True
            self.save(update_fields=['statut', 'sinistres_bloques', 'updated_at'])
            return True
        return False

    def get_expiration_phase(self):
        """Retourne la phase d'alerte (J-30, J-15, J-7, J0, post)."""
        jours = self.jours_restants
        if jours > 30:
            return None
        if jours > 15:
            return 'J30'
        if jours > 7:
            return 'J15'
        if jours > 0:
            return 'J7'
        if jours == 0:
            return 'J0'
        return 'POST'
