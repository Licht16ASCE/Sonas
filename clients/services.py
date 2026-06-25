from clients.models import ActiviteClient


def log_client_activity(client, type_activite, description, user=None):
    """Enregistre une activité dans l'historique client."""
    ActiviteClient.objects.create(
        client=client,
        type_activite=type_activite,
        description=description,
        created_by=user,
    )
