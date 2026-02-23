"""
Vues API REST pour les notifications in-app.

Endpoints :
  GET   /api/notifications/              → liste mes notifications (paginée)
  GET   /api/notifications/?is_read=false → notifications non lues
  PATCH /api/notifications/<id>/lire/    → marquer une notification comme lue
  POST  /api/notifications/tout_lire/    → marquer toutes les notifications comme lues

Toutes les routes nécessitent d'être authentifié.
Un utilisateur ne voit que SES notifications.
"""
from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer


# ═══════════════════════════════════════════════════════════════
# VUE API — Liste des notifications
# GET /api/notifications/
# ═══════════════════════════════════════════════════════════════

class NotificationListeAPIView(generics.ListAPIView):
    """
    GET : liste des notifications de l'utilisateur connecté.
    Supporte le filtre ?is_read=false pour les non lues uniquement.
    """
    serializer_class   = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Retourne les notifications de l'utilisateur.
        Filtre optionnel : ?is_read=false → uniquement les non lues.
        """
        qs = Notification.objects.filter(
            utilisateur=self.request.user
        ).order_by('-date_creation')

        # Filtre optionnel par statut de lecture
        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            # Conversion string → bool ('false' → False, 'true' → True)
            qs = qs.filter(is_read=is_read.lower() == 'true')

        return qs


# ═══════════════════════════════════════════════════════════════
# VUE API — Marquer une notification comme lue
# PATCH /api/notifications/<id>/lire/
# ═══════════════════════════════════════════════════════════════

class MarquerLuAPIView(APIView):
    """
    PATCH /api/notifications/<id>/lire/
    Marque une notification comme lue.
    Vérifie que la notification appartient à l'utilisateur connecté.
    """
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        try:
            notif = Notification.objects.get(pk=pk, utilisateur=request.user)
        except Notification.DoesNotExist:
            return Response(
                {'detail': 'Notification introuvable.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if notif.is_read:
            return Response(
                {'detail': 'Notification déjà lue.'},
                status=status.HTTP_200_OK
            )

        notif.is_read = True
        notif.save(update_fields=['is_read'])

        # Nombre de notifications non lues restantes (pour mettre à jour le badge)
        unread_count = Notification.objects.filter(
            utilisateur=request.user, is_read=False
        ).count()

        return Response(
            {
                'detail'      : 'Notification marquée comme lue.',
                'unread_count': unread_count,
            },
            status=status.HTTP_200_OK
        )


# ═══════════════════════════════════════════════════════════════
# VUE API — Marquer TOUTES les notifications comme lues
# POST /api/notifications/tout_lire/
# ═══════════════════════════════════════════════════════════════

class ToutLireAPIView(APIView):
    """
    POST /api/notifications/tout_lire/
    Marque toutes les notifications non lues de l'utilisateur comme lues.
    Pratique pour le bouton "Tout marquer comme lu" dans la navbar.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # update() en masse = une seule requête SQL (performant)
        updated = Notification.objects.filter(
            utilisateur=request.user,
            is_read=False
        ).update(is_read=True)

        return Response(
            {
                'detail'      : f'{updated} notification(s) marquée(s) comme lue(s).',
                'unread_count': 0,
            },
            status=status.HTTP_200_OK
        )