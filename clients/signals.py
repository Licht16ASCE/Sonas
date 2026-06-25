from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import User, UserRole
from .models import Client


@receiver(post_save, sender=User)
def create_client_profile(sender, instance, created, **kwargs):
    """Crée automatiquement un profil client pour les utilisateurs CLIENT."""
    if created and instance.role == UserRole.CLIENT:
        Client.objects.get_or_create(user=instance)
