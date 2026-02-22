"""
HooYia Market — reviews/serializers.py
Serializers pour les avis clients.

- AvisListSerializer   → lecture légère (liste d'avis sur un produit)
- AvisDetailSerializer → lecture complète (détail d'un avis)
- AvisCreerSerializer  → validation + création d'un avis
                         Vérifie que le client a bien reçu le produit (commande LIVREE)
"""
from rest_framework import serializers
from django.db import IntegrityError

from .models import Avis
from apps.orders.models import Commande


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Liste (lecture légère)
# Utilisé pour afficher les avis sur la fiche produit
# ═══════════════════════════════════════════════════════════════

class AvisListSerializer(serializers.ModelSerializer):
    """
    Sérialise un avis pour l'affichage en liste.
    Utilisé pour la fiche produit (clients) et le tableau de modération (admin).
    """

    nom_utilisateur = serializers.CharField(source='utilisateur.username', read_only=True)
    auteur          = serializers.CharField(source='utilisateur.username', read_only=True)
    auteur_nom      = serializers.CharField(source='utilisateur.username', read_only=True)
    produit_nom     = serializers.CharField(source='produit.nom', read_only=True)

    # Photo de profil : URL complète si elle existe, sinon None
    auteur_photo = serializers.SerializerMethodField()

    def get_auteur_photo(self, obj):
        request = self.context.get('request')
        photo = obj.utilisateur.photo_profil
        if photo and request:
            return request.build_absolute_uri(photo.url)
        return None

    class Meta:
        model  = Avis
        fields = [
            'id',
            'nom_utilisateur',  # Pour la fiche produit (frontend client)
            'auteur',           # Pour le dashboard admin
            'auteur_nom',       # Pour la carte avis (fiche produit)
            'auteur_photo',     # URL photo de profil (None si absente)
            'produit_nom',      # Pour le dashboard admin
            'note',
            'commentaire',
            'is_validated',
            'date_creation',
        ]
        read_only_fields = fields


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Détail (lecture complète, admin)
# ═══════════════════════════════════════════════════════════════

class AvisDetailSerializer(serializers.ModelSerializer):
    """
    Sérialise un avis complet.
    Inclut le statut de validation — utilisé dans l'admin ou
    pour les vues réservées aux admins.
    """

    nom_utilisateur = serializers.CharField(
        source='utilisateur.username',
        read_only=True
    )
    nom_produit = serializers.CharField(
        source='produit.nom',
        read_only=True
    )

    class Meta:
        model  = Avis
        fields = [
            'id',
            'nom_utilisateur',
            'nom_produit',
            'note',
            'commentaire',
            'is_validated',          # Visible uniquement en mode détail / admin
            'date_creation',
            'date_modification',
        ]
        read_only_fields = fields


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Créer un avis (écriture)
# Contient la validation métier complète
# ═══════════════════════════════════════════════════════════════

class AvisCreerSerializer(serializers.ModelSerializer):
    """
    Valide et crée un avis client.

    Validations effectuées :
      1. Le produit doit exister et être actif
      2. Le client doit avoir une commande LIVREE contenant ce produit
         (on ne peut pas noter un produit qu'on n'a pas reçu)
      3. Le client ne doit pas avoir déjà laissé un avis sur ce produit
         (géré par unique_together au niveau DB, mais on renvoie un message clair)
    """

    class Meta:
        model  = Avis
        fields = [
            'produit',      # FK → ID du produit (obligatoire)
            'note',         # 1 à 5 (obligatoire)
            'commentaire',  # Texte libre (facultatif)
        ]

    def validate_produit(self, produit):
        """
        Vérifie que le produit est actif et peut recevoir des avis.
        Appelé automatiquement par DRF lors de la validation du champ 'produit'.
        """
        # Un produit épuisé ou inactif ne devrait plus recevoir d'avis
        if produit.statut not in ['actif', 'stock_faible']:
            raise serializers.ValidationError(
                "Ce produit n'accepte plus d'avis."
            )
        return produit

    def validate(self, data):
        """
        Validation globale (cross-fields) — accès au contexte de la requête.

        Vérifie que l'utilisateur connecté a bien commandé et reçu le produit.
        Cette règle garantit que seuls les vrais acheteurs peuvent noter.
        """
        utilisateur = self.context['request'].user
        produit     = data['produit']

        # ── Vérification : l'utilisateur n'est pas admin/staff/vendeur ────────
        # Couche de sécurité supplémentaire côté serializer (la permission EstClient
        # bloque déjà en amont, mais on double-protège au cas où l'API serait
        # appelée directement sans passer par la vue standard).
        if utilisateur.is_staff or utilisateur.is_admin or utilisateur.is_vendeur:
            raise serializers.ValidationError(
                "Les administrateurs et vendeurs ne peuvent pas laisser d'avis. "
                "Cette fonctionnalité est réservée aux clients."
            )

        # ── Vérification : l'utilisateur a-t-il reçu ce produit ? ─────────────
        # Contrôlé par le flag AVIS_ACHAT_REQUIS dans settings.py.
        # En production : True → seuls les vrais acheteurs peuvent noter.
        # En développement : False → n'importe quel client peut laisser un avis.
        from django.conf import settings
        if getattr(settings, 'AVIS_ACHAT_REQUIS', False):
            a_commande = Commande.objects.filter(
                client=utilisateur,
                statut=Commande.LIVREE,
                lignes__produit=produit
            ).exists()

            if not a_commande:
                raise serializers.ValidationError(
                    "Vous ne pouvez laisser un avis que sur un produit que vous avez reçu."
                )

        # ── Vérification : l'utilisateur n'a-t-il pas déjà noté ce produit ? ──
        # Double sécurité : la DB lève IntegrityError (unique_together),
        # mais on préfère intercepter ici pour renvoyer un message clair en JSON.
        deja_note = Avis.objects.filter(
            utilisateur=utilisateur,
            produit=produit
        ).exists()

        if deja_note:
            raise serializers.ValidationError(
                "Vous avez déjà laissé un avis sur ce produit."
            )

        return data

    def create(self, validated_data):
        """
        Crée l'avis en associant automatiquement l'utilisateur connecté.
        is_validated=False par défaut (défini dans le modèle).

        L'utilisateur ne se saisit pas lui-même : on le récupère du contexte
        de la requête → évite qu'un client crée un avis au nom d'un autre.
        """
        try:
            return Avis.objects.create(
                utilisateur=self.context['request'].user,
                **validated_data
            )
        except IntegrityError:
            # Cas de concurrence rare : deux requêtes simultanées du même user
            raise serializers.ValidationError(
                "Vous avez déjà laissé un avis sur ce produit."
            )