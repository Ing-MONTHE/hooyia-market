"""
HooYia Market — products/api_views.py
Vues API REST pour les produits.
Retournent du JSON consommé par JavaScript.
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.cache import cache
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Produit, Categorie, ImageProduit, MouvementStock
from .serializers import (
    ProduitListSerializer,
    ProduitDetailSerializer,
    ProduitCreateUpdateSerializer,
    CategorieSerializer,
    ImageProduitSerializer,
    MouvementStockSerializer
)
from .filters import ProduitFilter
from apps.users.permissions import EstVendeur, EstProprietaire


# ═══════════════════════════════════════════════════════════════
# VIEWSET — Catégories
# GET /api/produits/categories/
# ═══════════════════════════════════════════════════════════════

class CategorieViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Lecture seule — tout le monde peut voir les catégories.
    Retourne uniquement les catégories racines avec
    leurs sous-catégories imbriquées.
    """
    serializer_class   = CategorieSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        # Cache 1h — les catégories changent rarement
        cache_key = 'categories_api'
        queryset  = cache.get(cache_key)
        if not queryset:
            queryset = Categorie.objects.filter(
                parent=None,
                est_active=True
            ).prefetch_related('sous_categories')
            cache.set(cache_key, queryset, 3600)
        return queryset


# ═══════════════════════════════════════════════════════════════
# VIEWSET — Produits
# ═══════════════════════════════════════════════════════════════

class ProduitViewSet(viewsets.ModelViewSet):
    """
    API complète pour les produits.

    GET    /api/produits/          → liste paginée + filtres
    POST   /api/produits/          → créer un produit (vendeur/admin)
    GET    /api/produits/<id>/     → détail produit
    PUT    /api/produits/<id>/     → modifier produit (owner)
    DELETE /api/produits/<id>/     → supprimer produit (admin)

    Actions spéciales :
    GET  /api/produits/en_vedette/ → produits en vedette
    POST /api/produits/<id>/ajouter_image/ → ajouter une image
    POST /api/produits/<id>/gerer_stock/   → modifier le stock
    """

    # Filtres, recherche et tri
    filter_backends  = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class  = ProduitFilter
    search_fields    = ['nom', 'description', 'categorie__nom']
    ordering_fields  = ['prix', 'date_creation', 'note_moyenne', 'stock']
    ordering         = ['-date_creation']  # Tri par défaut

    def get_queryset(self):
        """
        Retourne les produits selon le rôle de l'utilisateur :
        - Visiteur / Client → produits actifs uniquement
        - Vendeur → ses propres produits (tous statuts)
        - Admin → tous les produits
        """
        user = self.request.user

        if user.is_authenticated and user.is_admin:
            # Admin voit tout
            return Produit.objects.all().select_related(
                'categorie', 'vendeur'
            ).prefetch_related('images')

        if user.is_authenticated and user.is_vendeur:
            # Vendeur voit ses propres produits
            return Produit.objects.filter(
                vendeur=user
            ).select_related('categorie').prefetch_related('images')

        # Public → produits actifs uniquement
        return Produit.actifs.all()

    def get_serializer_class(self):
        """
        Choisit le serializer selon l'action :
        - list     → ProduitListSerializer (léger)
        - retrieve → ProduitDetailSerializer (complet)
        - create/update → ProduitCreateUpdateSerializer
        """
        if self.action == 'list':
            return ProduitListSerializer
        if self.action == 'retrieve':
            return ProduitDetailSerializer
        return ProduitCreateUpdateSerializer

    def get_permissions(self):
        """
        Permissions selon l'action :
        - Lecture (list, retrieve) → tout le monde
        - Création → vendeur ou admin
        - Modification → propriétaire ou admin
        - Suppression → admin uniquement
        """
        if self.action in ['list', 'retrieve', 'en_vedette']:
            return [permissions.AllowAny()]
        if self.action == 'create':
            return [permissions.IsAuthenticated(), EstVendeur()]
        if self.action in ['update', 'partial_update']:
            return [permissions.IsAuthenticated()]
        if self.action == 'destroy':
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

    def retrieve(self, request, *args, **kwargs):
        """
        Détail produit avec cache Redis 10 minutes.
        """
        instance  = self.get_object()
        cache_key = f'produit_{instance.pk}'
        data      = cache.get(cache_key)

        if not data:
            serializer = self.get_serializer(instance)
            data       = serializer.data
            cache.set(cache_key, data, 600)

        return Response(data)

    # ── Action spéciale : produits en vedette ─────────────────
    @action(detail=False, methods=['get'], url_path='en_vedette')
    def en_vedette(self, request):
        """
        GET /api/produits/en_vedette/
        Retourne les produits en vedette pour la page d'accueil.
        Cache 5 minutes.
        """
        data = cache.get('produits_vedette')
        if not data:
            produits   = Produit.vedette.all()[:8]  # Max 8 produits
            serializer = ProduitListSerializer(
                produits, many=True, context={'request': request}
            )
            data = serializer.data
            cache.set('produits_vedette', data, 300)
        return Response(data)

    # ── Action spéciale : ajouter une image ──────────────────
    @action(
        detail=True, methods=['post'],
        url_path='ajouter_image',
        permission_classes=[permissions.IsAuthenticated]
    )
    def ajouter_image(self, request, pk=None):
        """
        POST /api/produits/<id>/ajouter_image/
        Permet d'ajouter une image à un produit existant.
        """
        produit = self.get_object()

        # Vérifie que c'est le propriétaire ou un admin
        if produit.vendeur != request.user and not request.user.is_admin:
            return Response(
                {'erreur': 'Permission refusée.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = ImageProduitSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(produit=produit)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # ── Action spéciale : gérer le stock ─────────────────────
    @action(
        detail=True, methods=['post'],
        url_path='gerer_stock',
        permission_classes=[permissions.IsAuthenticated]
    )
    def gerer_stock(self, request, pk=None):
        """
        POST /api/produits/<id>/gerer_stock/
        Permet à un admin/vendeur de modifier le stock.
        Body : { "type_mouvement": "entree", "quantite": 50, "note": "..." }
        """
        produit = self.get_object()

        # Vérifie les permissions
        if not (request.user.is_admin or produit.vendeur == request.user):
            return Response(
                {'erreur': 'Permission refusée.'},
                status=status.HTTP_403_FORBIDDEN
            )

        type_mouvement = request.data.get('type_mouvement')
        quantite       = int(request.data.get('quantite', 0))
        note           = request.data.get('note', '')

        if quantite <= 0:
            return Response(
                {'erreur': 'La quantité doit être supérieure à 0.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Calcule le nouveau stock
        stock_avant = produit.stock
        if type_mouvement in ['entree', 'retour']:
            stock_apres = stock_avant + quantite
        elif type_mouvement == 'sortie':
            if quantite > stock_avant:
                return Response(
                    {'erreur': 'Stock insuffisant.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            stock_apres = stock_avant - quantite
        elif type_mouvement == 'ajustement':
            stock_apres = quantite  # Ajustement direct
        else:
            return Response(
                {'erreur': 'Type de mouvement invalide.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Crée le mouvement de stock dans une transaction
        with transaction.atomic():
            MouvementStock.objects.create(
                produit        = produit,
                type_mouvement = type_mouvement,
                quantite       = quantite,
                stock_avant    = stock_avant,
                stock_apres    = stock_apres,
                note           = note,
                effectue_par   = request.user
            )
            # Le signal mettre_a_jour_stock_produit met à jour le produit

        return Response({
            'message'    : 'Stock mis à jour.',
            'stock_avant': stock_avant,
            'stock_apres': stock_apres
        })