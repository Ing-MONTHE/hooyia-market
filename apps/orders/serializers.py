"""
HooYia Market — orders/serializers.py
Serializers pour les commandes.

- LigneCommandeSerializer    → une ligne d'une commande
- PaiementSerializer         → le paiement associé
- CommandeListSerializer     → liste légère (historique)
- CommandeDetailSerializer   → détail complet d'une commande
- CreerCommandeSerializer    → validation pour créer une commande
"""
from rest_framework import serializers
from .models import Commande, LigneCommande, Paiement


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Ligne de commande
# ═══════════════════════════════════════════════════════════════

class LigneCommandeSerializer(serializers.ModelSerializer):
    """
    Sérialise une ligne d'une commande.
    Inclut le sous-total calculé pour affichage.
    """

    # Propriété calculée : quantite × prix_unitaire
    sous_total = serializers.ReadOnlyField()

    class Meta:
        model  = LigneCommande
        fields = [
            'id', 'produit', 'produit_nom',
            'quantite', 'prix_unitaire', 'sous_total',
        ]
        # Tout est en lecture seule : une ligne de commande ne se modifie pas
        read_only_fields = fields


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Paiement
# ═══════════════════════════════════════════════════════════════

class PaiementSerializer(serializers.ModelSerializer):
    """
    Sérialise les informations de paiement d'une commande.
    """

    # Libellé lisible du mode de paiement (ex: "Paiement à la livraison")
    mode_affiche   = serializers.CharField(source='get_mode_display',   read_only=True)
    # Libellé lisible du statut (ex: "En attente")
    statut_affiche = serializers.CharField(source='get_statut_display', read_only=True)

    class Meta:
        model  = Paiement
        fields = [
            'id', 'mode', 'mode_affiche',
            'statut', 'statut_affiche',
            'montant', 'reference_externe',
            'date_paiement',
        ]
        read_only_fields = fields


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Liste des commandes (version légère)
# Utilisé pour l'historique des commandes.
# ═══════════════════════════════════════════════════════════════

class CommandeListSerializer(serializers.ModelSerializer):
    """
    Version allégée pour la liste des commandes.
    Affiche uniquement les informations essentielles pour la liste.
    """

    # Libellé lisible du statut
    statut_affiche = serializers.CharField(source='get_statut_display', read_only=True)

    # Référence courte (8 premiers caractères du UUID) pour affichage
    reference_courte = serializers.ReadOnlyField()

    class Meta:
        model  = Commande
        fields = [
            'id', 'reference', 'reference_courte',
            'statut', 'statut_affiche',
            'montant_total',
            'adresse_livraison_ville', 'adresse_livraison_pays',
            'date_creation',
        ]
        read_only_fields = fields


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Détail d'une commande (version complète)
# Utilisé pour la page de confirmation et le suivi de commande.
# ═══════════════════════════════════════════════════════════════

class CommandeDetailSerializer(serializers.ModelSerializer):
    """
    Version complète incluant les lignes, le paiement et toute l'adresse.
    """

    # Lignes de la commande imbriquées
    lignes           = LigneCommandeSerializer(many=True, read_only=True)
    # Paiement imbriqué
    paiement         = PaiementSerializer(read_only=True)
    # Libellés lisibles
    statut_affiche   = serializers.CharField(source='get_statut_display', read_only=True)
    reference_courte = serializers.ReadOnlyField()
    peut_etre_annulee = serializers.ReadOnlyField()

    class Meta:
        model  = Commande
        fields = [
            'id', 'reference', 'reference_courte',
            'statut', 'statut_affiche', 'peut_etre_annulee',
            'montant_total',
            # Adresse de livraison complète
            'adresse_livraison_nom', 'adresse_livraison_telephone',
            'adresse_livraison_adresse', 'adresse_livraison_ville',
            'adresse_livraison_region', 'adresse_livraison_pays',
            'note_client',
            'lignes', 'paiement',
            'date_creation', 'date_modification', 'date_livraison',
        ]
        read_only_fields = fields


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Création d'une commande
# Valide les données envoyées par le client lors du checkout.
# ═══════════════════════════════════════════════════════════════

class CreerCommandeSerializer(serializers.Serializer):
    """
    Valide les données pour créer une commande depuis le panier.

    Body JSON attendu :
      {
        "adresse_id"    : 1,           ← ID de l'adresse de livraison
        "mode_paiement" : "livraison", ← mode de paiement
        "note_client"   : "..."        ← optionnel
      }
    """

    adresse_id = serializers.IntegerField(
        min_value=1,
        help_text="ID de l'adresse de livraison choisie"
    )

    mode_paiement = serializers.ChoiceField(
        choices=Paiement.ModePaiement.choices,
        default=Paiement.ModePaiement.LIVRAISON,
        help_text="Mode de paiement"
    )

    note_client = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        default='',
        help_text="Instructions de livraison (optionnel)"
    )