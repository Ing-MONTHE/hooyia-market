"""
Serializers pour le panier.

Rôle des serializers ici :
  - PanierItemSerializer      → sérialise une ligne du panier (lecture + écriture)
  - PanierSerializer          → sérialise le panier complet avec toutes ses lignes
  - AjouterItemSerializer     → valide les données pour ajouter un article au panier
  - ModifierQuantiteSerializer → valide les données pour changer une quantité
"""
from rest_framework import serializers
from .models import Panier, PanierItem


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Article du panier (une ligne)
# ═══════════════════════════════════════════════════════════════

class PanierItemSerializer(serializers.ModelSerializer):
    """
    Sérialise une ligne du panier.
    Ajoute des infos du produit pour affichage (nom, image...) sans
    charger le serializer produit complet (performances).
    """

    # Infos du produit affichées côté client (lecture seule)
    produit_nom    = serializers.CharField(source='produit.nom',        read_only=True)
    produit_slug   = serializers.CharField(source='produit.slug',       read_only=True)
    produit_statut = serializers.CharField(source='produit.statut',     read_only=True)
    stock_disponible = serializers.IntegerField(source='produit.stock', read_only=True)

    # Propriété calculée du modèle (quantite × prix_snapshot)
    sous_total = serializers.ReadOnlyField()

    # Image principale du produit pour affichage dans le panier
    image_principale = serializers.SerializerMethodField()

    class Meta:
        model  = PanierItem
        fields = [
            'id',
            'produit', 'produit_nom', 'produit_slug',
            'produit_statut', 'stock_disponible',
            'quantite', 'prix_snapshot', 'sous_total',
            'image_principale',
            'date_ajout',
        ]
        # Le prix snapshot est défini au moment de l'ajout, pas modifiable ensuite
        read_only_fields = ['prix_snapshot', 'date_ajout', 'sous_total']

    def get_image_principale(self, obj):
        """Retourne l'URL de l'image principale du produit"""
        if not obj.produit:
            return None
        image = (
            obj.produit.images.filter(est_principale=True).first()
            or obj.produit.images.first()
        )
        if image:
            # build_absolute_uri construit l'URL complète (avec http://localhost:8000)
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(image.image.url)
            return image.image.url
        return None


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Panier complet
# ═══════════════════════════════════════════════════════════════

class PanierSerializer(serializers.ModelSerializer):
    """
    Sérialise le panier complet avec toutes ses lignes.
    Retourné par GET /api/panier/.
    Inclut le total et le nombre d'articles calculés.
    """

    # Toutes les lignes du panier, imbriquées
    items           = PanierItemSerializer(many=True, read_only=True)

    # Propriétés calculées du modèle Panier
    total           = serializers.ReadOnlyField()
    nombre_articles = serializers.ReadOnlyField()
    est_vide        = serializers.ReadOnlyField()

    class Meta:
        model  = Panier
        fields = [
            'id',
            'items',
            'total', 'nombre_articles', 'est_vide',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Ajout d'un article au panier
# ═══════════════════════════════════════════════════════════════

class AjouterItemSerializer(serializers.Serializer):
    """
    Valide les données envoyées pour ajouter un produit au panier.
    Utilisé par POST /api/panier/ajouter/.

    Body JSON attendu :
      { "produit_id": 5, "quantite": 2 }
    """

    produit_id = serializers.IntegerField(
        min_value=1,
        help_text="ID du produit à ajouter"
    )
    quantite = serializers.IntegerField(
        default=1,
        min_value=1,
        max_value=100,   # Limite raisonnable pour éviter les abus
        help_text="Quantité souhaitée (défaut : 1)"
    )


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Modification de quantité
# ═══════════════════════════════════════════════════════════════

class ModifierQuantiteSerializer(serializers.Serializer):
    """
    Valide les données pour modifier la quantité d'une ligne.
    Utilisé par PATCH /api/panier/items/<id>/.

    Body JSON attendu :
      { "quantite": 3 }

    Si quantite = 0, la ligne sera supprimée (géré dans CartService).
    """

    quantite = serializers.IntegerField(
        min_value=0,    # 0 = suppression de la ligne
        max_value=100,
        help_text="Nouvelle quantité (0 pour supprimer l'article)"
    )