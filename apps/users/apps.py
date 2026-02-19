"""
On connecte les signals ici pour qu'ils soient
chargés au démarrage de Django.
Sans ça, les signals n'écoutent rien du tout.
"""
from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users'
    verbose_name = 'Utilisateurs'

    def ready(self):
        # Importe les signals → Django les enregistre au démarrage
        import apps.users.signals