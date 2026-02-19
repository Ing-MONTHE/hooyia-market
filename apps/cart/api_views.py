"""
HooYia Market — cart/api_views.py
Vues API REST pour le panier.
Retournent du JSON consommé par JavaScript (fetch API).

Endpoints gérés :
  GET    /api/panier/              → voir son panier
  POST   /api/panier/ajouter/      → ajouter un article
  PATCH  /api/panier/items/<id>/   → modifier la quantité
  DELETE /api/panier/items/<id>/   → supprimer un article
  DELETE /api/panier/vider/        → vider tout le panier

Toutes ces routes nécessitent d'être authentifié (IsAuthenticated).
Le panier est toujours celui de l'utilisateur connecté,
on ne peut jamais accéder au panier d'un autre utilisateur.
"""
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.core.exceptions import ValidationError

from .models import Panier, PanierItem
from .serializers import (
    PanierSerializer,
    PanierItemSerializer,
    AjouterItemSerializer,
    ModifierQuantiteSerializer,
)
from .services import CartService


# ═══════════════════════════════════════════════════════════════
# VUE API — Panier de l'utilisateur connecté
# GET /api/panier/
# ═══════════════════════════════════════════════════════════════

class PanierAPIView(APIView):
    """
    Retourne le panier complet de l'utilisateur connecté.
    Inclut toutes les lignes avec les infos des produits,
    les sous-totaux et le total général.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        GET /api/panier/
        Récupère ou crée le panier de l'utilisateur connecté.
        get_or_create : si le panier n'existe pas encore (cas rare), on le crée.
        """
        # get_or_create retourne (instance, created_bool)
        panier, _ = Panier.objects.get_or_create(utilisateur=request.user)

        serializer = PanierSerializer(panier, context={'request': request})
        return Response(serializer.data)


# ═══════════════════════════════════════════════════════════════
# VUE API — Ajouter un article au panier
# POST /api/panier/ajouter/
# ═══════════════════════════════════════════════════════════════

class AjouterItemAPIView(APIView):
    """
    Ajoute un produit au panier de l'utilisateur connecté.
    Si le produit est déjà dans le panier, la quantité est augmentée.
    Toute la logique métier est dans CartService.add_item().
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        POST /api/panier/ajouter/
        Body attendu : { "produit_id": 5, "quantite": 2 }
        """
        # Valide les données reçues
        serializer = AjouterItemSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Récupère ou crée le panier
        panier, _ = Panier.objects.get_or_create(utilisateur=request.user)

        try:
            # Délègue toute la logique au service
            item = CartService.add_item(
                panier     = panier,
                produit_id = serializer.validated_data['produit_id'],
                quantite   = serializer.validated_data['quantite'],
            )
        except ValidationError as e:
            # CartService lève une ValidationError si le produit est indisponible
            # ou si la quantité dépasse le stock
            return Response(
                {'erreur': e.message},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Retourne la ligne créée/mise à jour et le résumé du panier
        return Response({
            'message'        : 'Article ajouté au panier.',
            'item'           : PanierItemSerializer(item, context={'request': request}).data,
            'nombre_articles': panier.nombre_articles,
            'total'          : str(panier.total),
        }, status=status.HTTP_201_CREATED)


# ═══════════════════════════════════════════════════════════════
# VUE API — Modifier ou supprimer une ligne du panier
# PATCH  /api/panier/items/<id>/
# DELETE /api/panier/items/<id>/
# ═══════════════════════════════════════════════════════════════

class PanierItemAPIView(APIView):
    """
    Modifie la quantité ou supprime une ligne du panier.
    Vérifie toujours que la ligne appartient au panier de l'utilisateur connecté.
    """
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        """
        PATCH /api/panier/items/<id>/
        Body attendu : { "quantite": 3 }
        Si quantite = 0, la ligne est supprimée.
        """
        serializer = ModifierQuantiteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Récupère le panier de l'utilisateur connecté
        try:
            panier = request.user.panier
        except Panier.DoesNotExist:
            return Response(
                {'erreur': 'Panier introuvable.'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            item = CartService.update_quantity(
                panier            = panier,
                item_id           = pk,
                nouvelle_quantite = serializer.validated_data['quantite'],
            )
        except ValidationError as e:
            return Response({'erreur': e.message}, status=status.HTTP_400_BAD_REQUEST)

        # Si quantite = 0, CartService retourne None (ligne supprimée)
        if item is None:
            return Response({
                'message'        : 'Article supprimé du panier.',
                'nombre_articles': panier.nombre_articles,
                'total'          : str(panier.total),
            })

        return Response({
            'message'        : 'Quantité mise à jour.',
            'item'           : PanierItemSerializer(item, context={'request': request}).data,
            'nombre_articles': panier.nombre_articles,
            'total'          : str(panier.total),
        })

    def delete(self, request, pk):
        """
        DELETE /api/panier/items/<id>/
        Supprime complètement une ligne du panier.
        """
        try:
            panier = request.user.panier
        except Panier.DoesNotExist:
            return Response(
                {'erreur': 'Panier introuvable.'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            CartService.remove_item(panier=panier, item_id=pk)
        except ValidationError as e:
            return Response({'erreur': e.message}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'message'        : 'Article supprimé du panier.',
            'nombre_articles': panier.nombre_articles,
            'total'          : str(panier.total),
        }, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════
# VUE API — Vider complètement le panier
# DELETE /api/panier/vider/
# ═══════════════════════════════════════════════════════════════

class ViderPanierAPIView(APIView):
    """
    Supprime tous les articles du panier en une seule opération.
    Le panier lui-même est conservé (prêt pour la prochaine commande).
    """
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        """
        DELETE /api/panier/vider/
        Vide entièrement le panier de l'utilisateur connecté.
        """
        try:
            panier = request.user.panier
        except Panier.DoesNotExist:
            return Response(
                {'erreur': 'Panier introuvable.'},
                status=status.HTTP_404_NOT_FOUND
            )

        panier.vider()  # Supprime tous les PanierItem (méthode du modèle)

        return Response(
            {'message': 'Panier vidé avec succès.'},
            status=status.HTTP_200_OK
        )