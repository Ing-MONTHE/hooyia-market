from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.audit'

    def ready(self):
        # Charge tous les signals d'audit métier au démarrage de Django
        import apps.audit.signals  # noqa: F401