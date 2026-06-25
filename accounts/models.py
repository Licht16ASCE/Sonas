from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    CLIENT = 'CLIENT', 'Client'
    AGENT = 'AGENT', 'Agent'
    GERANT = 'GERANT', 'Gérant'
    ADMIN = 'ADMIN', 'Administrateur'


class User(AbstractUser):
    """Utilisateur SONAS avec rôle métier."""

    role = models.CharField(
        max_length=10,
        choices=UserRole.choices,
        default=UserRole.CLIENT,
        db_index=True,
    )
    phone = models.CharField(max_length=20, blank=True)
    theme_preference = models.CharField(
        max_length=10,
        choices=[('light', 'Clair'), ('dark', 'Sombre'), ('system', 'Système')],
        default='system',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'

    def __str__(self):
        return f'{self.get_full_name() or self.username} ({self.get_role_display()})'

    @property
    def is_client(self):
        return self.role == UserRole.CLIENT

    @property
    def is_agent(self):
        return self.role == UserRole.AGENT

    @property
    def is_gerant(self):
        return self.role == UserRole.GERANT

    @property
    def is_admin_user(self):
        return self.role == UserRole.ADMIN

    @property
    def is_internal(self):
        return self.role in (UserRole.AGENT, UserRole.GERANT, UserRole.ADMIN)

    def get_dashboard_url(self):
        if self.is_client:
            return '/client/'
        return '/sonas/'
