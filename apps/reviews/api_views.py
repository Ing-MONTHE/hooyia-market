"""
Vues API JSON pour les avis clients.

Endpoints exposés (préfixe défini dans config/urls.py : api/avis/) :
  GET    /api/avis/                → liste des avis validés (public)
  POST   /api/avis/                → créer un avis (authentifié, acheteur vérifié)
  GET    /api/avis/<id>/           → détail d'un avis
  DELETE /api/avis/<id>/           → supprimer son propre avis (ou admin)

  Actions admin :
  POST   /api/avis/<id>/valider/   → valide un avis (admin seulement)
  POST   /api/avis/<id>/invalider/ → invalide un avis (admin seulement)
"""
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import Avis
from .serializers import AvisListSerializer, AvisDetailSerializer, AvisCreerSerializer
from apps.users.permissions import EstClient


# ═══════════════════════════════════════════════════════════════
# VIEWSET — Avis
# ═══════════════════════════════════════════════════════════════

class AvisViewSet(viewsets.ModelViewSet):
    """
    ViewSet complet pour les avis clients.

    Permissions :
      - Lecture (GET) : tout le monde (seuls les avis validés sont exposés)
      - Création (POST) : tout utilisateur authentifié (avec vérification achat)
      - Suppression (DELETE) : le propriétaire de l'avis ou un admin
      - Actions valider/invalider : admin seulement

    Queryset selon le rôle :
      - Admin (is_staff)       → TOUS les avis (validés + en attente)
      - Utilisateur connecté   → avis validés + SES propres avis non validés
      - Anonyme                → uniquement les avis validés
    """

    # Filtre par produit : GET /api/avis/?produit=42
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['produit']

    # ── Queryset de base ──────────────────────────────────────────────────────
    # Surcharge complète dans get_queryset() → ce queryset sert uniquement
    # à satisfaire Django qui exige un queryset de classe défini.
    queryset = Avis.objects.all()

    def get_queryset(self):
        """
        Retourne le queryset filtré selon le rôle de l'utilisateur.

        La logique de visibilité :
          - Admin → tout voir (pour modérer les avis en attente)
          - Utilisateur → avis validés publics + ses propres avis (pour voir son avis
            en attente et pouvoir le modifier ou le supprimer)
          - Anonyme → uniquement les avis validés
        """
        # Base : toujours avec select_related pour éviter les requêtes N+1
        qs = Avis.objects.select_related('utilisateur', 'produit').order_by('-date_creation')

        user = self.request.user

        # Admin : accès complet (validés + non validés de tous les utilisateurs)
        if user.is_authenticated and user.is_staff:
            return qs

        # Utilisateur connecté : avis validés + ses propres avis non validés
        if user.is_authenticated:
            from django.db.models import Q
            return qs.filter(
                Q(is_validated=True) | Q(utilisateur=user)
            )

        # Anonyme : uniquement les avis validés (publication publique)
        return qs.filter(is_validated=True)

    def get_permissions(self):
        """
        Permissions différentes selon l'action :
          - list / retrieve      : tout le monde (public)
          - create               : clients uniquement (admins/vendeurs exclus)
          - destroy              : authentifié (propriétaire ou admin vérifié dans perform_destroy)
          - valider / invalider  : admin seulement
        """
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        if self.action in ['valider', 'invalider']:
            return [permissions.IsAdminUser()]
        if self.action == 'create':
            # Seuls les clients peuvent laisser un avis
            # Les admins/vendeurs gèrent les produits mais ne peuvent pas les noter
            return [EstClient()]
        # destroy → authentifié (propriétaire ou admin géré dans perform_destroy)
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        """
        Choix du serializer selon le contexte :
          - Création → AvisCreerSerializer (contient la validation métier)
          - Détail   → AvisDetailSerializer (inclut is_validated, dates)
          - Liste    → AvisListSerializer (allégé pour l'affichage public)
        """
        if self.action == 'create':
            return AvisCreerSerializer
        if self.action == 'retrieve':
            return AvisDetailSerializer
        return AvisListSerializer

    def perform_destroy(self, instance):
        """
        Suppression d'un avis : vérifie que l'utilisateur est le propriétaire ou admin.
        Le signal post_delete (reviews/signals.py) recalculera automatiquement
        la note_moyenne et nombre_avis du produit.
        """
        user = self.request.user

        # Seul le propriétaire ou un admin peut supprimer l'avis
        if not user.is_staff and instance.utilisateur != user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Vous ne pouvez supprimer que votre propre avis.")

        instance.delete()

    # ── Action : valider un avis ───────────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='valider')
    def valider(self, request, pk=None):
        """
        POST /api/avis/<id>/valider/
        Valide un avis (admin seulement — permission vérifiée dans get_permissions).
        Déclenche le signal post_save → recalcul de note_moyenne du produit.
        """
        avis = self.get_object()

        if avis.is_validated:
            return Response(
                {'detail': 'Cet avis est déjà validé.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        avis.is_validated = True
        avis.save(update_fields=['is_validated'])
        # Le signal post_save (reviews/signals.py) recalcule automatiquement note_moyenne

        return Response(
            {'detail': f'Avis #{avis.id} validé. Note moyenne du produit mise à jour.'},
            status=status.HTTP_200_OK
        )

    # ── Action : invalider un avis ─────────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='invalider')
    def invalider(self, request, pk=None):
        """
        POST /api/avis/<id>/invalider/
        Invalide un avis (admin seulement — pour modération).
        Déclenche le signal post_save → recalcul de note_moyenne sans cet avis.
        """
        avis = self.get_object()

        if not avis.is_validated:
            return Response(
                {'detail': 'Cet avis est déjà invalide.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        avis.is_validated = False
        avis.save(update_fields=['is_validated'])
        # Le signal post_save (reviews/signals.py) recalcule automatiquement note_moyenne

        return Response(
            {'detail': f'Avis #{avis.id} invalidé. Note moyenne du produit recalculée.'},
            status=status.HTTP_200_OK
        )