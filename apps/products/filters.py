"""
HooYia Market — products/filters.py

Filtres django-filter pour l'API produits.
Permet de filtrer les produits via les paramètres URL :
  /api/produits/?categorie=1&prix_min=5000&prix_max=50000&note_min=4
"""
import django_filters
from .models import Produit, Categorie


class ProduitFilter(django_filters.FilterSet):
    """
    Filtre complet pour les produits.
    Chaque champ correspond à un paramètre URL.
    """

    # Filtre par fourchette de prix
    # ?prix_min=5000&prix_max=100000
    prix_min = django_filters.NumberFilter(
        field_name='prix',
        lookup_expr='gte',   # gte = greater than or equal (>=)
        label="Prix minimum"
    )
    prix_max = django_filters.NumberFilter(
        field_name='prix',
        lookup_expr='lte',   # lte = less than or equal (<=)
        label="Prix maximum"
    )

    # Filtre par note minimum
    # ?note_min=4 → produits avec note >= 4
    note_min = django_filters.NumberFilter(
        field_name='note_moyenne',
        lookup_expr='gte',
        label="Note minimum"
    )

    # Filtre par catégorie (slug ou id)
    # ?categorie=telephonie
    categorie = django_filters.ModelChoiceFilter(
        queryset=Categorie.objects.filter(est_active=True),
        field_name='categorie',
        label="Catégorie"
    )

    # Filtre par slug exact du produit
    # ?slug=samsung-galaxy-s24
    slug = django_filters.CharFilter(
        field_name='slug',
        lookup_expr='exact',
        label="Slug produit"
    )

    # Filtre par slug de catégorie (inclut sous-catégories via MPTT)
    # ?categorie_slug=telephonie
    categorie_slug = django_filters.CharFilter(
        method='filter_categorie_slug',
        label="Slug catégorie"
    )

    def filter_categorie_slug(self, queryset, name, value):
        try:
            cat = Categorie.objects.get(slug=value, est_active=True)
            descendants = cat.get_descendants(include_self=True)
            return queryset.filter(categorie__in=descendants)
        except Categorie.DoesNotExist:
            return queryset.none()

    # Filtre produits en stock uniquement
    # ?en_stock=true
    en_stock = django_filters.BooleanFilter(
        field_name='stock',
        method='filter_en_stock',
        label="En stock uniquement"
    )

    # Filtre produits en vedette
    # ?en_vedette=true
    en_vedette = django_filters.BooleanFilter(
        field_name='en_vedette',
        label="En vedette"
    )

    # Filtre par vendeur
    # ?vendeur=3
    vendeur = django_filters.NumberFilter(
        field_name='vendeur__id',
        label="Vendeur (ID)"
    )

    def filter_en_stock(self, queryset, name, value):
        """Filtre personnalisé pour les produits en stock"""
        if value:
            return queryset.filter(stock__gt=0)
        return queryset

    class Meta:
        model  = Produit
        fields = [
            'statut', 'en_vedette',
            'categorie', 'vendeur'
        ]