"""
Modèle pour stocker les logs en base de données
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class AuditLog(models.Model):

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_logs',
        verbose_name=_("Utilisateur")
    )

    action = models.CharField(max_length=10, verbose_name=_("Action"))
    url = models.CharField(max_length=255, verbose_name=_("URL"))
    status_code = models.IntegerField(verbose_name=_("Code HTTP"))
    date = models.DateTimeField(auto_now_add=True, verbose_name=_("Date"))
    note = models.TextField(blank=True, verbose_name=_("Note"))

    class Meta:
        ordering = ['-date']
        verbose_name = _('Log Audit')
        verbose_name_plural = _('Logs Audit')

    def __str__(self):
        return f"{self.action} | {self.url} | {self.utilisateur} | {self.date}"