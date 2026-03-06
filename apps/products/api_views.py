"""
Vues API REST pour les produits.
Retournent du JSON consommé par JavaScript.
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django.core.cache import cache
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Produit, Categorie, MouvementStock
from .serializers import (
    ProduitListSerializer,
    ProduitDetailSerializer,
    ProduitCreateUpdateSerializer,
    CategorieSerializer,
    ImageProduitSerializer
)
from .filters import ProduitFilter
from apps.users.permissions import EstVendeur, EstAdminOuLectureSeule



# ═══════════════════════════════════════════════════════════════
# PAGINATION — Inclut page_size dans la réponse pour le JS
# ═══════════════════════════════════════════════════════════════
class AdminPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'count':     self.page.paginator.count,
            'next':      self.get_next_link(),
            'previous':  self.get_previous_link(),
            'page_size': self.page_size,
            'results':   data,
        })


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
    pagination_class = AdminPagination
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
    search_fields    = ['nom', 'description', 'categorie__nom', 'slug']
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

        if user.is_authenticated and (getattr(user, 'is_admin', False) or user.is_staff):
            # Admin voit tout
            return Produit.objects.all().select_related(
                'categorie', 'vendeur'
            ).prefetch_related('images', 'mouvements_stock')

        if user.is_authenticated and getattr(user, 'is_vendeur', False):
            # Vendeur voit tous les produits actifs (pour consulter le catalogue)
            # + ses propres produits (tous statuts, pour gérer son stock)
            from django.db.models import Q
            return Produit.objects.filter(
                Q(statut='actif') | Q(vendeur=user)
            ).distinct().select_related('categorie', 'vendeur').prefetch_related('images', 'mouvements_stock')

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
            return [permissions.IsAuthenticated(), EstAdminOuLectureSeule()]
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

    def perform_update(self, serializer):
        """
        Override pour gérer les images lors d'un PATCH/PUT.
        Les fichiers envoyés dans request.FILES['images'] sont ajoutés au produit.
        """
        from .models import ImageProduit
        instance = serializer.save()
        images = self.request.FILES.getlist('images')
        for i, img_file in enumerate(images):
            est_principale = (not instance.images.exists() and i == 0)
            ImageProduit.objects.create(
                produit=instance,
                image=img_file,
                ordre=instance.images.count(),
                est_principale=est_principale,
            )
        # Invalider le cache
        cache.delete(f'produit_{instance.pk}')
        cache.delete(f'produit_slug_{instance.slug}')

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
        if produit.vendeur != request.user and not (request.user.is_admin or request.user.is_staff):
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
        if not (request.user.is_admin or request.user.is_staff or produit.vendeur == request.user):
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

# ═══════════════════════════════════════════════════════════════
# VUE — Stats Overview Dashboard Admin
# GET /api/stats/overview/
# ═══════════════════════════════════════════════════════════════
from rest_framework.views import APIView
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, Count, F, Q

class StatsOverviewView(APIView):
    """
    Agrégat de statistiques pour le tableau de bord admin.
    Retourne KPIs, commandes récentes, alertes stock, activité.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        import traceback, logging
        logger = logging.getLogger(__name__)
        try:
            return self._get_data(request)
        except Exception as e:
            logger.error("StatsOverviewView 500: %s\n%s", e, traceback.format_exc())
            return Response({'error': str(e), 'detail': traceback.format_exc()}, status=500)

    def _get_data(self, request):
        from apps.orders.models import Commande
        from apps.users.models import CustomUser
        from apps.reviews.models import Avis
        from apps.cart.models import Panier
        from apps.audit.models import AuditLog

        maintenant = timezone.now()
        debut_mois = maintenant.replace(day=1, hour=0, minute=0, second=0)

        # ── KPIs principaux ──
        produits_actifs  = Produit.objects.filter(statut=Produit.Statut.ACTIF).count()
        produits_total   = Produit.objects.count()
        commandes_total  = Commande.objects.count()
        utilisateurs     = CustomUser.objects.filter(is_active=True).count()
        nouveaux_users   = CustomUser.objects.filter(date_inscription__gte=debut_mois).count()
        avis_total       = Avis.objects.count()

        # ── Alertes ──
        commandes_attente = Commande.objects.filter(statut=Commande.EN_ATTENTE).count()
        try:
            avis_en_attente = Avis.objects.filter(is_validated=False).count()
        except Exception:
            try:
                avis_en_attente = Avis.objects.filter(is_valide=False).count()
            except Exception:
                avis_en_attente = 0

        # ── Stocks ──
        stock_faible = Produit.objects.filter(
            stock__gt=0, stock__lte=F('stock_minimum')
        ).count()
        stock_epuise = Produit.objects.filter(stock=0).count()

        # ── Commandes récentes (5) — champ FK = 'client' ──
        commandes_recentes = []
        for c in Commande.objects.select_related('client').order_by('-date_creation')[:5]:
            try:
                client_nom = (c.client.get_full_name() or c.client.username) if c.client else '—'
            except Exception:
                client_nom = '—'
            commandes_recentes.append({
                'id':              c.id,
                'reference_courte': str(c.reference)[:8].upper() if c.reference else str(c.id).zfill(6),
                'client_nom':      client_nom,
                'montant_total':   str(c.montant_total),
                'date_creation':   c.date_creation.isoformat(),
                'statut':          c.statut,
            })

        # ── Stocks faibles (6) ──
        stocks_faibles = []
        for p in Produit.objects.filter(stock__lte=F('stock_minimum')).order_by('stock')[:6]:
            stocks_faibles.append({
                'id':            p.id,
                'nom':           p.nom,
                'stock':         p.stock,
                'stock_minimum': p.stock_minimum,
                'stock_max':     (p.stock_minimum * 3) or 15,
            })

        # ── Activité récente (AuditLog — champ date, pas date_action) ──
        activite_recente = []
        try:
            for log in AuditLog.objects.select_related('utilisateur').order_by('-date')[:6]:
                activite_recente.append({
                    'description': f"{log.action} — {log.url}",
                    'date':        log.date.isoformat(),
                    'type':        'systeme',
                })
        except Exception:
            pass

        # ── Vue système ──
        try:
            from apps.chat.models import Conversation
            conversations = Conversation.objects.count()
        except Exception:
            conversations = 0

        try:
            from apps.notifications.models import Notification
            notifications_total = Notification.objects.count()
        except Exception:
            notifications_total = 0

        try:
            paniers_actifs = Panier.objects.filter(items__isnull=False).distinct().count()
        except Exception:
            paniers_actifs = 0

        return Response({
            # KPIs
            'produits_actifs':    produits_actifs,
            'produits_total':     produits_total,
            'commandes_total':    commandes_total,
            'utilisateurs':       utilisateurs,
            'nouveaux_users':     nouveaux_users,
            'avis_total':         avis_total,
            # Alertes
            'commandes_attente':  commandes_attente,
            'avis_en_attente':    avis_en_attente,
            # Stocks
            'stock_faible':       stock_faible,
            'stock_epuise':       stock_epuise,
            # Listes
            'commandes_recentes': commandes_recentes,
            'stocks_faibles':     stocks_faibles,
            'activite_recente':   activite_recente,
            # Système
            'conversations':       conversations,
            'notifications_total': notifications_total,
            'paniers_actifs':      paniers_actifs,
        })