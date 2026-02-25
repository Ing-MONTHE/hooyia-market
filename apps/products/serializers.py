"""
Serializers pour les produits :
- CategorieSerializer        → arbre des catégories
- ImageProduitSerializer     → images d'un produit
- ProduitListSerializer      → liste légère (catalogue)
- ProduitDetailSerializer    → fiche complète
- ProduitCreateUpdateSerializer → création/modification
- MouvementStockSerializer   → historique stock
"""
from rest_framework import serializers
from .models import Produit, Categorie, ImageProduit, MouvementStock


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Catégorie
# ═══════════════════════════════════════════════════════════════

class CategorieSerializer(serializers.ModelSerializer):
    """
    Sérialise une catégorie avec ses sous-catégories.
    La récursivité permet de retourner tout l'arbre en une seule requête.
    """

    # Sous-catégories imbriquées (récursif)
    sous_categories = serializers.SerializerMethodField()
    nombre_produits = serializers.SerializerMethodField()

    class Meta:
        model  = Categorie
        fields = [
            'id', 'nom', 'slug', 'description',
            'image', 'parent', 'sous_categories',
            'nombre_produits', 'est_active'
        ]

    def get_sous_categories(self, obj):
        """Retourne les sous-catégories de cette catégorie"""
        sous_cats = obj.sous_categories.filter(est_active=True)
        # Sérialisation récursive
        return CategorieSerializer(sous_cats, many=True, context=self.context).data

    def get_nombre_produits(self, obj):
        """Compte les produits actifs dans cette catégorie"""
        return obj.produits.filter(statut='actif').count()


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Image produit
# ═══════════════════════════════════════════════════════════════

class ImageProduitSerializer(serializers.ModelSerializer):
    """
    Sérialise les images d'un produit.
    Retourne l'URL complète de l'image.
    """

    class Meta:
        model  = ImageProduit
        fields = [
            'id', 'image', 'alt_text',
            'ordre', 'est_principale'
        ]


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Liste produits (version légère)
# Utilisé pour afficher la grille du catalogue.
# Ne charge que les champs nécessaires pour les performances.
# ═══════════════════════════════════════════════════════════════

class ProduitListSerializer(serializers.ModelSerializer):
    """
    Version allégée pour la liste des produits.
    Charge le minimum pour afficher une carte produit.
    """

    # Champs calculés via @property du modèle
    prix_actuel        = serializers.ReadOnlyField()
    est_en_stock       = serializers.ReadOnlyField()
    pourcentage_remise = serializers.ReadOnlyField()

    # Image principale uniquement
    image_principale = serializers.SerializerMethodField()

    # Nom de la catégorie (pas l'objet complet)
    categorie_nom = serializers.CharField(
        source='categorie.nom',
        read_only=True
    )

    # Stock maximum historique (pour calculer le % de remplissage correct)
    stock_max = serializers.SerializerMethodField()

    class Meta:
        model  = Produit
        fields = [
            'id', 'nom', 'slug',
            'prix', 'prix_promo', 'prix_actuel',
            'pourcentage_remise',
            'stock', 'stock_minimum', 'stock_max', 'est_en_stock',
            'note_moyenne', 'nombre_avis',
            'categorie_nom',
            'en_vedette', 'statut',
            'image_principale',
            'date_creation'
        ]

    def get_image_principale(self, obj):
        """Retourne uniquement l'image principale"""
        image = (
            obj.images.filter(est_principale=True).first()
            or obj.images.first()
        )
        if image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(image.image.url)
            return image.image.url
        return None

    def get_stock_max(self, obj):
        """
        Retourne le stock maximum historique (plus haute valeur stock_apres
        enregistrée dans MouvementStock), utilisé pour calculer le % de remplissage.
        Si aucun mouvement, fallback sur stock actuel.
        """
        from django.db.models import Max
        result = obj.mouvements_stock.aggregate(Max('stock_apres'))
        max_val = result.get('stock_apres__max')
        if max_val and max_val > 0:
            return max_val
        # Fallback : stock actuel (100% par défaut si pas d'historique)
        return max(obj.stock, 1)


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Détail produit (version complète)
# Utilisé pour la fiche produit individuelle.
# ═══════════════════════════════════════════════════════════════

class ProduitDetailSerializer(serializers.ModelSerializer):
    """
    Version complète pour la fiche d'un produit.
    Inclut toutes les images, la catégorie complète, le vendeur.
    """

    images             = ImageProduitSerializer(many=True, read_only=True)
    categorie          = CategorieSerializer(read_only=True)
    prix_actuel        = serializers.ReadOnlyField()
    est_en_stock       = serializers.ReadOnlyField()
    stock_faible       = serializers.ReadOnlyField()
    pourcentage_remise = serializers.ReadOnlyField()

    # Informations publiques du vendeur
    vendeur_nom = serializers.CharField(
        source='vendeur.username',
        read_only=True
    )

    class Meta:
        model  = Produit
        fields = [
            'id', 'nom', 'slug',
            'description', 'description_courte',
            'prix', 'prix_promo', 'prix_actuel',
            'pourcentage_remise',
            'stock', 'est_en_stock', 'stock_faible',
            'note_moyenne', 'nombre_avis',
            'categorie', 'vendeur_nom',
            'en_vedette', 'statut',
            'images',
            'date_creation', 'date_modification'
        ]


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Création / Modification produit
# Utilisé par les vendeurs et admins pour gérer les produits.
# ═══════════════════════════════════════════════════════════════

class ProduitCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Gère la création et modification d'un produit.
    Le vendeur est automatiquement associé via la vue.
    """

    class Meta:
        model  = Produit
        fields = [
            'nom', 'description', 'description_courte',
            'prix', 'prix_promo',
            'stock', 'stock_minimum',
            'categorie', 'statut', 'en_vedette'
        ]

    def validate_prix(self, value):
        """Le prix doit être positif"""
        if value <= 0:
            raise serializers.ValidationError(
                "Le prix doit être supérieur à 0."
            )
        return value

    def validate_prix_promo(self, value):
        """Le prix promo doit être inférieur au prix normal"""
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                "Le prix promotionnel doit être supérieur à 0."
            )
        return value

    def validate(self, attrs):
        """Vérifie que le prix promo est inférieur au prix normal"""
        prix       = attrs.get('prix')
        prix_promo = attrs.get('prix_promo')

        if prix and prix_promo and prix_promo >= prix:
            raise serializers.ValidationError({
                'prix_promo': "Le prix promotionnel doit être inférieur au prix normal."
            })
        return attrs

    def create(self, validated_data):
        """
        Associe automatiquement le vendeur connecté au produit.
        """
        validated_data['vendeur'] = self.context['request'].user
        return super().create(validated_data)


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Mouvement de stock
# ═══════════════════════════════════════════════════════════════

class MouvementStockSerializer(serializers.ModelSerializer):
    """
    Sérialise les mouvements de stock.
    Utilisé pour l'historique et la gestion du stock admin.
    """

    effectue_par_nom = serializers.CharField(
        source='effectue_par.username',
        read_only=True
    )

    class Meta:
        model  = MouvementStock
        fields = [
            'id', 'produit', 'type_mouvement',
            'quantite', 'stock_avant', 'stock_apres',
            'note', 'effectue_par_nom', 'date'
        ]
        read_only_fields = ['stock_avant', 'stock_apres', 'date']