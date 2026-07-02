from django.conf import settings
from django.db import models


class Client(models.Model):
    """Profil client lié à un compte utilisateur."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='client_profile',
    )
    raison_sociale = models.CharField(max_length=200, blank=True)
    siret = models.CharField(max_length=14, blank=True)
    adresse = models.TextField(blank=True)
    code_postal = models.CharField(max_length=10, blank=True)
    ville = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    notes_internes = models.TextField(blank=True, help_text='Visible uniquement en interne')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'
        ordering = ['-created_at']

    def __str__(self):
        name = self.raison_sociale or self.user.get_full_name() or self.user.username
        return name

    @property
    def display_name(self):
        return self.__str__()

    @property
    def email(self):
        return self.user.email

    @property
    def ville_affichage(self):
        """Ville du profil, ou à défaut celle du bien le plus récent."""
        if self.ville.strip():
            return self.ville
        biens = list(self.biens.all())
        if not biens:
            return ''
        return max(biens, key=lambda b: b.created_at).ville

    @property
    def localisation_affichage(self):
        """Code postal + ville pour l'espace interne."""
        if self.code_postal.strip() or self.ville.strip():
            return ' '.join(p for p in (self.code_postal, self.ville) if p).strip()
        biens = list(self.biens.all())
        if not biens:
            return ''
        bien = max(biens, key=lambda b: b.created_at)
        return ' '.join(p for p in (bien.code_postal, bien.ville) if p).strip()


class ActiviteClient(models.Model):
    """Historique des activités client."""

    class TypeActivite(models.TextChoices):
        CONNEXION = 'CONNEXION', 'Connexion'
        BIEN_CREE = 'BIEN_CREE', 'Bien déclaré'
        CONTRAT_CREE = 'CONTRAT_CREE', 'Contrat créé'
        SINISTRE_DECLARE = 'SINISTRE_DECLARE', 'Sinistre déclaré'
        DOCUMENT_UPLOAD = 'DOCUMENT_UPLOAD', 'Document uploadé'
        PROFIL_MODIFIE = 'PROFIL_MODIFIE', 'Profil modifié'
        AUTRE = 'AUTRE', 'Autre'

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='activites')
    type_activite = models.CharField(max_length=20, choices=TypeActivite.choices)
    description = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Activité client'
        verbose_name_plural = 'Activités clients'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.client} — {self.get_type_activite_display()}'
