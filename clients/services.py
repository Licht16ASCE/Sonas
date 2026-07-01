from clients.models import ActiviteClient


def log_client_activity(client, type_activite, description, user=None):
    """Enregistre une activité dans l'historique client."""
    ActiviteClient.objects.create(
        client=client,
        type_activite=type_activite,
        description=description,
        created_by=user,
    )


def sync_client_location_from_bien(bien):
    """Recopie la localisation du bien sur le profil client si absent."""
    client = bien.client
    update_fields = []
    if not client.ville.strip() and bien.ville:
        client.ville = bien.ville
        update_fields.append('ville')
    if not client.code_postal.strip() and bien.code_postal:
        client.code_postal = bien.code_postal
        update_fields.append('code_postal')
    if not client.adresse.strip() and bien.adresse:
        client.adresse = bien.adresse
        update_fields.append('adresse')
    if update_fields:
        update_fields.append('updated_at')
        client.save(update_fields=update_fields)
