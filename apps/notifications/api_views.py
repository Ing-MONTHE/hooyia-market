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
from django.utils.translation import gettext as _

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

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Retourne les notifications de l'utilisateur.
        Filtre optionnel : ?is_read=false → uniquement les non lues.
        """
        qs = Notification.objects.filter(utilisateur=self.request.user).order_by(
            "-date_creation"
        )

        # Filtre optionnel par statut de lecture
        is_read = self.request.query_params.get("is_read")
        if is_read is not None:
            # Conversion string → bool ('false' → False, 'true' → True)
            qs = qs.filter(is_read=is_read.lower() == "true")

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
                {"detail": _("Notification introuvable.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        if notif.is_read:
            return Response(
                {"detail": _("Notification déjà lue.")}, status=status.HTTP_200_OK
            )

        notif.is_read = True
        notif.save(update_fields=["is_read"])

        # Nombre de notifications non lues restantes (pour mettre à jour le badge)
        unread_count = Notification.objects.filter(
            utilisateur=request.user, is_read=False
        ).count()

        return Response(
            {
                "detail": _("Notification marquée comme lue."),
                "unread_count": unread_count,
            },
            status=status.HTTP_200_OK,
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
            utilisateur=request.user, is_read=False
        ).update(is_read=True)

        return Response(
            {
                "detail": _("%(n)s notification(s) marquée(s) comme lue(s).")
                % {"n": updated},
                "unread_count": 0,
            },
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════
# VUE API ADMIN — Toutes les notifications (admin dashboard)
# GET /api/notifications/admin/
# ═══════════════════════════════════════════════════════════════


class NotificationAdminListeAPIView(generics.ListAPIView):
    """
    GET : liste de toutes les notifications (admin uniquement).
    Utilisé par le dashboard admin pour la section Notifications.
    """

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not (user.is_staff or getattr(user, "is_admin", False)):
            return Notification.objects.none()

        qs = Notification.objects.select_related("utilisateur").order_by(
            "-date_creation"
        )

        # Filtre optionnel par type
        type_notif = self.request.query_params.get("type", "")
        if type_notif:
            qs = qs.filter(type_notif=type_notif)

        # Filtre par statut de lecture
        is_read = self.request.query_params.get("is_read", "")
        if is_read:
            qs = qs.filter(is_read=is_read.lower() == "true")

        return qs


# ═══════════════════════════════════════════════════════════════
# VUE API ADMIN — Envoyer une notification manuelle
# POST /api/notifications/envoyer/
# ═══════════════════════════════════════════════════════════════


class EnvoyerNotificationAdminAPIView(APIView):
    """
    POST : envoie une notification manuelle depuis le dashboard admin.

    Body JSON :
      {
        "destinataire": "tous" | "client" | <user_id>,
        "type_notif"  : "commande" | "avis" | "stock" | "systeme",
        "titre"       : "Titre de la notification",
        "message"     : "Corps du message",
        "lien"        : "/url/optionnel/"   (optionnel)
      }

    Réponse :
      { "envoye": <nb>, "message": "..." }
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if not (user.is_staff or getattr(user, "is_admin", False)):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied()

        from apps.users.models import CustomUser
        from apps.notifications.tasks import _diffuser_notification_ws

        destinataire = request.data.get("destinataire", "tous")
        type_notif = request.data.get("type_notif", "systeme")
        titre = request.data.get("titre", "").strip()
        message = request.data.get("message", "").strip()
        lien = request.data.get("lien", "").strip()

        if not titre or not message:
            return Response(
                {"erreur": "Le titre et le message sont obligatoires."}, status=400
            )

        # ── Déterminer les destinataires ──────────────────────
        if destinataire == "tous":
            users = CustomUser.objects.filter(is_active=True)
        elif destinataire == "clients":
            users = CustomUser.objects.filter(is_active=True, is_staff=False).exclude(
                is_admin=True
            )
        elif destinataire == "admins":
            users = CustomUser.objects.filter(is_active=True, is_staff=True)
        else:
            # ID utilisateur spécifique
            try:
                users = CustomUser.objects.filter(pk=int(destinataire), is_active=True)
            except (ValueError, TypeError):
                return Response({"erreur": "Destinataire invalide."}, status=400)

        nb = 0
        for u in users:
            try:
                _diffuser_notification_ws(
                    utilisateur_id=u.id,
                    titre=titre,
                    message=message,
                    type_notif=type_notif,
                    lien=lien,
                )
                nb += 1
            except Exception:
                pass

        return Response(
            {"envoye": nb, "message": f"{nb} notification(s) envoyée(s) avec succès."}
        )
