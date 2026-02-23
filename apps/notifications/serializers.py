"""
Serializers pour les notifications in-app.

- NotificationSerializer       → lecture d'une notification
- MarquerLuSerializer          → marquer une notification comme lue
"""
from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """
    Sérialise une notification pour l'affichage dans la liste.
    Inclut le libellé lisible du type (ex: 'Commande' au lieu de 'commande').
    """

    # Libellé human-readable du type de notification
    type_label = serializers.CharField(source='get_type_notif_display', read_only=True)

    class Meta:
        model  = Notification
        fields = [
            'id',
            'titre',
            'message',
            'type_notif',    # Code (commande, avis, stock, systeme)
            'type_label',    # Libellé lisible (Commande, Avis, Stock, Système)
            'is_read',
            'lien',
            'date_creation',
        ]
        read_only_fields = fields