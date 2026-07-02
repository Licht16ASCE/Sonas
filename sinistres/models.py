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
    plafond_indemnisation = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Plafond d\'indemnisation applicable à ce sinistre.',
    )
    montant_indemnise = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Montant effectivement indemnisé après validation.',
    )
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
    indemnisation_accordee = models.BooleanField(
        null=True,
        blank=True,
        help_text='Décision agent : une indemnisation est-elle accordée pour ce sinistre ?',
    )
    montant_indemnisation_propose = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Montant proposé par l\'agent pour indemnisation.',
    )
    notes_traitement = models.TextField(
        blank=True,
        help_text='Notes internes de l\'agent sur le traitement du dossier.',
    )
    traite_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sinistres_traites',
    )
    soumis_validation = models.BooleanField(
        default=False,
        help_text='Dossier transmis au gérant pour validation finale.',
    )
    date_soumission = models.DateTimeField(null=True, blank=True)
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
        if self.plafond_indemnisation is None and self.contrat_id:
            self.plafond_indemnisation = self.contrat.plafond_disponible
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

    @property
    def rapport_indemnisation(self):
        return self.rapports_indemnisation.order_by('-created_at').first()

    @property
    def en_attente_validation_gerant(self):
        return self.statut == SinistreStatut.EN_COURS and self.soumis_validation

    @property
    def statut_display_detail(self):
        if self.en_attente_validation_gerant:
            return 'En attente validation gérant'
        return self.get_statut_display()


class RapportIndemnisation(models.Model):
    """Rapport d'indemnisation généré automatiquement à la validation du sinistre."""

    sinistre = models.ForeignKey(
        Sinistre,
        on_delete=models.CASCADE,
        related_name='rapports_indemnisation',
    )
    reference = models.CharField(max_length=50, unique=True)
    montant_demande = models.DecimalField(max_digits=12, decimal_places=2)
    montant_indemnise = models.DecimalField(max_digits=12, decimal_places=2)
    montant_non_couvert = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    plafond_sinistre = models.DecimalField(max_digits=12, decimal_places=2)
    plafond_contrat_avant = models.DecimalField(max_digits=12, decimal_places=2)
    plafond_contrat_apres = models.DecimalField(max_digits=12, decimal_places=2)
    depassement_detecte = models.BooleanField(default=False)
    contrat_invalide = models.BooleanField(default=False)
    contenu = models.TextField()
    document = models.ForeignKey(
        'documents.Document',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rapports_indemnisation',
    )
    genere_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='rapports_indemnisation_generes',
    )
    copie_client_envoyee = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Rapport d\'indemnisation'
        verbose_name_plural = 'Rapports d\'indemnisation'
        ordering = ['-created_at']

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f'RPT-{uuid.uuid4().hex[:8].upper()}'
        super().save(*args, **kwargs)
