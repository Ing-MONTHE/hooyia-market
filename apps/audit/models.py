"""
HooYia Market — audit/models.py
Modèle pour stocker les logs en base de données
"""
from django.db import models
from django.conf import settings


class AuditLog(models.Model):
    """
    Enregistre chaque action importante dans la base de données.
    Qui a fait quoi, quand, et depuis quelle URL.
    """

    # L'utilisateur qui a effectué l'action (null si anonyme)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_logs'
    )

    # Type d'action : CREATE, UPDATE, DELETE
    action = models.CharField(max_length=10)

    # URL concernée
    url = models.CharField(max_length=255)

    # Code de réponse HTTP (200, 201, 404...)
    status_code = models.IntegerField()

    # Date et heure automatiques
    date = models.DateTimeField(auto_now_add=True)

    # Informations supplémentaires (optionnel)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Log Audit'
        verbose_name_plural = 'Logs Audit'

    def __str__(self):
        return f"{self.action} | {self.url} | {self.utilisateur} | {self.date}"