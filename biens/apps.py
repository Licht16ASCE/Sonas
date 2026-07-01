from django.apps import AppConfig


class BiensConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'biens'
    verbose_name = 'Biens immobiliers'

    def ready(self):
        import biens.signals  # noqa: F401
