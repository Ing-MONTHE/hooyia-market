"""
HooYia Market — reviews/api_views.py
Vues API JSON pour les avis clients.

Endpoints exposés :
  GET    /api/avis/?produit=<id>  → liste des avis validés d'un produit
  POST   /api/avis/               → créer un avis (authentifié, acheteur vérifié)
  GET    /api/avis/<id>/          → détail d'un avis
  DELETE /api/avis/<id>/          → supprimer son propre avis (ou admin)

  Actions admin :
  POST   /api/avis/<id>/valider/    → valide un avis (admin seulement)
  POST   /api/avis/<id>/invalider/  → invalide un avis (admin seulement)
"""
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import Avis
from .serializers import AvisListSerializer, AvisDetailSerializer, AvisCreerSerializer


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
    """

    # Filtre de base : seuls les avis validés sont visibles publiquement
    # L'admin voit tout via l'interface Django Admin (pas via cette API)
    queryset = Avis.objects.filter(is_validated=True).select_related(
        'utilisateur',  # Pour afficher le nom sans requête supplémentaire
        'produit'       # Pour afficher le nom du produit si besoin
    ).order_by('-date_creation')

    # Filtre par produit : GET /api/avis/?produit=42
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['produit']

    def get_permissions(self):
        """
        Permissions différentes selon l'action :
          - list / retrieve : tout le monde (public)
          - create          : authentifié (la vérification achat est dans le serializer)
          - destroy         : authentifié (propriétaire ou admin vérifié dans perform_destroy)
          - valider / invalider : admin seulement
        """
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        if self.action in ['valider', 'invalider']:
            return [permissions.IsAdminUser()]
        # create, destroy : authentifié
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

    def get_queryset(self):
        """
        Surcharge du queryset selon l'utilisateur :
          - Admin → voit TOUS les avis (validés ET non validés)
          - Utilisateur connecté → voit les avis validés + SES propres avis non validés
          - Anonyme → voit uniquement les avis validés

        Permet à un utilisateur de voir son propre avis en attente de validation.
        """
        qs = Avis.objects.select_related('utilisateur', 'produit').order_by('-date_creation')

        user = self.request.user

        if user.is_authenticated and user.is_staff:
            # Admin : tous les avis
            return qs

        if user.is_authenticated:
            # Utilisateur : avis validés + ses propres avis
            from django.db.models import Q
            return qs.filter(
                Q(is_validated=True) | Q(utilisateur=user)
            )

        # Anonyme : uniquement les avis validés
        return qs.filter(is_validated=True)

    def perform_destroy(self, instance):
        """
        Suppression d'un avis : vérifie que l'utilisateur est le propriétaire ou admin.
        Le signal post_delete (reviews/signals.py) recalculera la note_moyenne.
        """
        user = self.request.user

        # Un utilisateur ne peut supprimer que SON avis
        if not user.is_staff and instance.utilisateur != user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Vous ne pouvez supprimer que votre propre avis.")

        instance.delete()

    # ── Action : valider un avis ───────────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='valider')
    def valider(self, request, pk=None):
        """
        POST /api/avis/<id>/valider/
        Valide un avis (admin seulement).
        Déclenche le signal → recalcul de note_moyenne du produit.
        """
        avis = self.get_object()

        if avis.is_validated:
            return Response(
                {'detail': 'Cet avis est déjà validé.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        avis.is_validated = True
        avis.save(update_fields=['is_validated'])
        # Le signal post_save recalcule automatiquement la note_moyenne

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
        Déclenche le signal → recalcul de note_moyenne sans cet avis.
        """
        avis = self.get_object()

        if not avis.is_validated:
            return Response(
                {'detail': 'Cet avis est déjà invalide.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        avis.is_validated = False
        avis.save(update_fields=['is_validated'])
        # Le signal post_save recalcule automatiquement la note_moyenne

        return Response(
            {'detail': f'Avis #{avis.id} invalidé. Note moyenne du produit recalculée.'},
            status=status.HTTP_200_OK
        )