from django.db.models.signals import post_save
from django.dispatch import receiver

from clients.services import sync_client_location_from_bien
from .models import Bien


@receiver(post_save, sender=Bien)
def sync_client_location_on_bien_save(sender, instance, **kwargs):
    sync_client_location_from_bien(instance)
