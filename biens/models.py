from django.db import models

from clients.models import Client


class BienStatut(models.TextChoices):
    EN_ATTENTE = 'EN_ATTENTE', 'En attente'
    VALIDE = 'VALIDE', 'Validé'
    REJETE = 'REJETE', 'Rejeté'


class BienType(models.TextChoices):
    APPARTEMENT = 'APPARTEMENT', 'Appartement'
    MAISON = 'MAISON', 'Maison'
    LOCAL_COMMERCIAL = 'LOCAL_COMMERCIAL', 'Local commercial'
    IMMEUBLE = 'IMMEUBLE', 'Immeuble'
    AUTRE = 'AUTRE', 'Autre'


class Bien(models.Model):
    """Bien immobilier lié à un client."""

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='biens')
    reference = models.CharField(max_length=50, unique=True)
    type_bien = models.CharField(max_length=20, choices=BienType.choices, default=BienType.APPARTEMENT)
    adresse = models.TextField()
    code_postal = models.CharField(max_length=10)
    ville = models.CharField(max_length=100)
    surface_m2 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    valeur_estimee = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Valeur estimée du bien en USD (utilisée pour la grille tarifaire).',
    )
    grille_tarifaire = models.ForeignKey(
        'contrats.GrilleTarifaire',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='biens',
        verbose_name='Forfait d\'assurance',
    )
    description = models.TextField(blank=True)
    statut = models.CharField(max_length=15, choices=BienStatut.choices, default=BienStatut.EN_ATTENTE)
    motif_rejet = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Bien'
        verbose_name_plural = 'Biens'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.reference} — {self.ville}'

    @property
    def is_validated(self):
        return self.statut == BienStatut.VALIDE
