from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class NotificationType(models.TextChoices):
    ACTION_PENDING = 'ACTION_PENDING', 'Action en attente'
    STATUT_CHANGE = 'STATUT_CHANGE', 'Changement de statut'
    CONTRAT_EXPIRATION = 'CONTRAT_EXPIRATION', 'Expiration contrat'
    DIGEST = 'DIGEST', 'Résumé quotidien'
    SYSTEM = 'SYSTEM', 'Système'


class NotificationPriority(models.TextChoices):
    LOW = 'low', 'Basse'
    NORMAL = 'normal', 'Normale'
    HIGH = 'high', 'Haute'
    CRITICAL = 'critical', 'Critique'


class Notification(models.Model):
    """Notification intelligente avec regroupement possible."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    type_notification = models.CharField(max_length=25, choices=NotificationType.choices)
    priority = models.CharField(
        max_length=10,
        choices=NotificationPriority.choices,
        default=NotificationPriority.NORMAL,
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    digest_key = models.CharField(max_length=100, blank=True, db_index=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['digest_key']),
        ]

    def __str__(self):
        return f'{self.title} — {self.user.username}'


class ActionType(models.TextChoices):
    SINISTRE_INCOMPLET = 'SINISTRE_INCOMPLET', 'Sinistre incomplet'
    CONTRAT_NON_FINALISE = 'CONTRAT_NON_FINALISE', 'Contrat non finalisé'
    DOCUMENTS_MANQUANTS = 'DOCUMENTS_MANQUANTS', 'Documents manquants'
    BIEN_INCOMPLET = 'BIEN_INCOMPLET', 'Bien incomplet'
    CONTRAT_EXPIRATION = 'CONTRAT_EXPIRATION', 'Renouvellement contrat'


class ActionEnAttente(models.Model):
    """Tâche incomplète à reprendre par l'utilisateur."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='actions_en_attente',
    )
    action_type = models.CharField(max_length=25, choices=ActionType.choices)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_resolved = models.BooleanField(default=False)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Action en attente'
        verbose_name_plural = 'Actions en attente'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_resolved']),
        ]

    def __str__(self):
        return self.title
