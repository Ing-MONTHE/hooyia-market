"""
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

    statut_affiche   = serializers.CharField(source='get_statut_display', read_only=True)
    reference_courte = serializers.ReadOnlyField()

    # Nom du client — utilisé dans le dashboard admin
    client_nom = serializers.SerializerMethodField()

    def get_client_nom(self, obj):
        u = obj.client
        if not u:
            return '—'
        full = f"{u.prenom} {u.nom}".strip()
        return full if full else u.username

    # Lignes légères pour l'historique client (nom produit + qté uniquement)
    lignes = LigneCommandeSerializer(many=True, read_only=True)

    class Meta:
        model  = Commande
        fields = [
            'id', 'reference', 'reference_courte',
            'statut', 'statut_affiche',
            'montant_total',
            'client_nom',
            'lignes',
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

    Accepte deux formats :

    Format 1 — adresse sauvegardée (FK) :
      { "adresse_id": 1, "mode_paiement": "livraison", "note_client": "..." }

    Format 2 — adresse inline (saisie directe depuis le checkout) :
      {
        "adresse_livraison_nom"      : "Jean Dupont",
        "adresse_livraison_telephone": "+237 600 000 000",
        "adresse_livraison_adresse"  : "Rue 123",
        "adresse_livraison_ville"    : "Yaoundé",
        "adresse_livraison_region"   : "Centre",
        "adresse_livraison_pays"     : "Cameroun",
        "mode_paiement"              : "livraison",
        "note_client"                : "..."
      }
    """

    # ── Format 1 : adresse sauvegardée ─────────────────────
    adresse_id = serializers.IntegerField(
        required=False,
        min_value=1,
        help_text="ID d'une adresse de livraison enregistrée"
    )

    # ── Format 2 : champs adresse inline ───────────────────
    adresse_livraison_nom       = serializers.CharField(required=False, max_length=150)
    adresse_livraison_telephone = serializers.CharField(required=False, max_length=20)
    adresse_livraison_adresse   = serializers.CharField(required=False, max_length=255)
    adresse_livraison_ville     = serializers.CharField(required=False, max_length=100)
    adresse_livraison_region    = serializers.CharField(required=False, max_length=100)
    adresse_livraison_pays      = serializers.CharField(required=False, max_length=100, default='Cameroun')

    # ── Commun ──────────────────────────────────────────────
    mode_paiement = serializers.ChoiceField(
        choices=Paiement.ModePaiement.choices,
        default=Paiement.ModePaiement.LIVRAISON,
    )

    note_client = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        default='',
    )

    def validate(self, data):
        """
        Vérifie qu'on a soit adresse_id, soit les champs inline obligatoires.
        """
        adresse_id = data.get('adresse_id')
        nom        = data.get('adresse_livraison_nom', '').strip()
        telephone  = data.get('adresse_livraison_telephone', '').strip()
        adresse    = data.get('adresse_livraison_adresse', '').strip()
        ville      = data.get('adresse_livraison_ville', '').strip()
        region     = data.get('adresse_livraison_region', '').strip()

        if not adresse_id:
            # Format inline : champs obligatoires
            manquants = []
            if not nom:       manquants.append('adresse_livraison_nom')
            if not telephone: manquants.append('adresse_livraison_telephone')
            if not adresse:   manquants.append('adresse_livraison_adresse')
            if not ville:     manquants.append('adresse_livraison_ville')
            if not region:    manquants.append('adresse_livraison_region')
            if manquants:
                raise serializers.ValidationError(
                    f"Champs obligatoires manquants : {', '.join(manquants)}"
                )
        return data