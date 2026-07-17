import os
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models

from biens.models import Bien, BienType
from clients.models import Client


def preuve_paiement_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    return f'preuves_paiement/{instance.contrat_id}/{uuid.uuid4().hex}{ext}'


class ContratStatut(models.TextChoices):
    EN_ATTENTE = 'EN_ATTENTE', 'En attente'
    BROUILLON = 'BROUILLON', 'Brouillon'
    ACTIF = 'ACTIF', 'Actif'
    INACTIF = 'INACTIF', 'Inactif'
    EXPIRE = 'EXPIRE', 'Expiré'
    RESILIE = 'RESILIE', 'Résilié'
    EPUISE = 'EPUISE', 'Inactif'  # rétrocompatibilité — migré vers INACTIF


class GrilleTarifaire(models.Model):
    """Grille de prix par type de bien / fourchette de valeur (USD)."""

    type_bien = models.CharField(max_length=30)
    libelle = models.CharField(max_length=120)
    valeur_min = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    valeur_max = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    prime_annuelle = models.DecimalField(max_digits=12, decimal_places=2)
    plafond_indemnisation = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Grille tarifaire'
        verbose_name_plural = 'Grilles tarifaires'
        ordering = ['type_bien', 'valeur_min']

    def __str__(self):
        return f'{self.libelle} ({self.type_bien})'

    def couvre_valeur(self, valeur):
        if valeur is None:
            return self.valeur_min == 0 and self.valeur_max is None
        valeur = Decimal(str(valeur))
        if valeur < self.valeur_min:
            return False
        if self.valeur_max is not None and valeur > self.valeur_max:
            return False
        return True

    @classmethod
    def trouver_pour(cls, type_bien, valeur=None):
        qs = cls.objects.filter(type_bien=type_bien, is_active=True).order_by('valeur_min')
        if valeur is None:
            return qs.filter(valeur_min=0).first() or qs.first()
        for grille in qs:
            if grille.couvre_valeur(valeur):
                return grille
        return qs.last()


class Contrat(models.Model):
    """Contrat liant un client à un bien."""

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='contrats')
    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name='contrats')
    reference = models.CharField(max_length=50, unique=True)
    date_debut = models.DateField()
    date_fin = models.DateField()
    statut = models.CharField(
        max_length=15,
        choices=ContratStatut.choices,
        default=ContratStatut.BROUILLON,
    )
    montant_annuel = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    plafond_indemnisation = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text='Plafond total d\'indemnisation du contrat (USD).',
    )
    montant_indemnise_cumule = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text='Montant total déjà indemnisé sur ce contrat (USD).',
    )
    grille_tarifaire = models.ForeignKey(
        GrilleTarifaire,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contrats',
        verbose_name='Forfait d\'assurance',
    )
    bon_paiement_reference = models.CharField(max_length=50, blank=True, db_index=True)
    paiement_valide = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    date_souscription = models.DateTimeField(null=True, blank=True)
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
        if not self.bon_paiement_reference:
            self.bon_paiement_reference = f'BP-{uuid.uuid4().hex[:10].upper()}'
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

    @property
    def is_inactif(self):
        return self.statut in (ContratStatut.INACTIF, ContratStatut.EPUISE)

    @property
    def documents_requis_complets(self):
        return self.bien.documents.exclude(
            type_document__in=('CONTRAT_PDF', 'BON_PAIEMENT', 'PREUVE_PAIEMENT', 'RETRAIT_BANCAIRE'),
        ).exists()

    @property
    def peut_etre_active(self):
        return (
            self.statut in (ContratStatut.EN_ATTENTE, ContratStatut.BROUILLON)
            and self.paiement_valide
            and self.documents_requis_complets
            and self.bien.statut == 'VALIDE'
        )

    @property
    def plafond_disponible(self):
        plafond = self.plafond_indemnisation or Decimal('0')
        utilise = self.montant_indemnise_cumule or Decimal('0')
        reste = plafond - utilise
        return reste if reste > 0 else Decimal('0')

    @property
    def plafond_epuise(self):
        if not self.plafond_indemnisation:
            return False
        return self.plafond_disponible <= Decimal('0')

    def deduire_indemnisation(self, montant):
        montant = Decimal(str(montant))
        self.montant_indemnise_cumule = (self.montant_indemnise_cumule or Decimal('0')) + montant
        self.save(update_fields=['montant_indemnise_cumule', 'updated_at'])

    def invalider_plafond(self, motif=''):
        self.statut = ContratStatut.INACTIF
        self.sinistres_bloques = True
        if motif:
            prefix = f'[{motif}] '
            self.notes = f'{prefix}{self.notes}'.strip() if self.notes else prefix.strip()
        self.save(update_fields=['statut', 'sinistres_bloques', 'notes', 'updated_at'])
        return True

    def check_and_update_expiration(self):
        today = date.today()
        if self.date_fin < today and self.statut == ContratStatut.ACTIF:
            self.statut = ContratStatut.EXPIRE
            self.sinistres_bloques = True
            self.save(update_fields=['statut', 'sinistres_bloques', 'updated_at'])
            return True
        return False

    def get_expiration_phase(self):
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

    @property
    def document_contractuel(self):
        return self.documents.filter(type_document='CONTRAT_PDF').order_by('-created_at').first()

    @property
    def document_bon_paiement(self):
        return self.documents.filter(type_document='BON_PAIEMENT').order_by('-created_at').first()


class PoliceAssurance(models.Model):
    """Police d'assurance générée automatiquement à la déclaration du bien."""

    reference = models.CharField(max_length=50, unique=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='polices')
    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name='polices')
    contrat = models.OneToOneField(Contrat, on_delete=models.CASCADE, related_name='police_assurance')
    type_assurance = models.CharField(max_length=30)
    prime_annuelle = models.DecimalField(max_digits=12, decimal_places=2)
    plafond_indemnisation = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Police d\'assurance'
        verbose_name_plural = 'Polices d\'assurance'
        ordering = ['-created_at']

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f'POL-{uuid.uuid4().hex[:8].upper()}'
        super().save(*args, **kwargs)


class PreuvePaiement(models.Model):
    """Preuve de paiement bancaire déposée par le client."""

    reference = models.CharField(max_length=50, unique=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='preuves_paiement')
    contrat = models.ForeignKey(Contrat, on_delete=models.CASCADE, related_name='preuves_paiement')
    fichier = models.FileField(upload_to=preuve_paiement_upload_path)
    document = models.ForeignKey(
        'documents.Document',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='preuves_paiement',
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='preuves_paiement_deposees',
    )
    is_validated = models.BooleanField(default=False)
    validee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='preuves_paiement_validees',
    )
    date_validation = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Preuve de paiement'
        verbose_name_plural = 'Preuves de paiement'
        ordering = ['-created_at']

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f'PRV-{uuid.uuid4().hex[:8].upper()}'
        super().save(*args, **kwargs)


def default_contrat_dates():
    today = date.today()
    return today, today + timedelta(days=365)


# Mapping type bien → libellé assurance
TYPE_ASSURANCE_LABELS = {
    BienType.APPARTEMENT: 'Assurance habitation — Appartement',
    BienType.MAISON: 'Assurance habitation — Maison',
    BienType.LOCAL_COMMERCIAL: 'Assurance locaux commerciaux',
    BienType.IMMEUBLE: 'Assurance immeuble',
    BienType.AUTRE: 'Assurance multirisque',
}
