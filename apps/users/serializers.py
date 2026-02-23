"""
Les serializers sont les "traducteurs" entre Python et JSON.
Ils font deux choses :
  1. Convertir un objet Python (modèle) → JSON (pour envoyer au frontend)
  2. Valider et convertir du JSON reçu → objet Python (pour sauvegarder en DB)
"""
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import CustomUser, AdresseLivraison


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Informations publiques d'un utilisateur
# Utilisé quand on affiche un profil (pas d'infos sensibles)
# ═══════════════════════════════════════════════════════════════

class UtilisateurPublicSerializer(serializers.ModelSerializer):
    """
    Version légère — uniquement les infos non sensibles.
    Utilisé par exemple pour afficher l'auteur d'un avis.
    """
    class Meta:
        model  = CustomUser
        fields = ['id', 'username', 'photo_profil', 'date_inscription']


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Profil complet de l'utilisateur connecté
# Utilisé pour afficher et modifier son propre profil
# ═══════════════════════════════════════════════════════════════

class ProfilSerializer(serializers.ModelSerializer):
    """
    Version complète — toutes les infos de l'utilisateur connecté.
    Les champs sensibles (password, is_admin...) sont exclus.
    """

    # Champ calculé : non stocké en DB, calculé à la volée
    nom_complet = serializers.SerializerMethodField()

    class Meta:
        model  = CustomUser
        fields = [
            'id', 'username', 'email',
            'nom', 'prenom', 'nom_complet',
            'telephone', 'photo_profil',
            'is_vendeur', 'email_verifie',
            'date_inscription'
        ]
        # Ces champs sont affichés mais non modifiables via l'API
        read_only_fields = ['email', 'email_verifie', 'date_inscription']

    def get_nom_complet(self, obj):
        """Retourne 'Prénom Nom' ou le username si pas renseigné"""
        return obj.get_full_name()


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Inscription d'un nouvel utilisateur
# Valide les données du formulaire d'inscription
# ═══════════════════════════════════════════════════════════════

class InscriptionSerializer(serializers.ModelSerializer):
    """
    Gère la création d'un nouveau compte utilisateur.
    Valide : format email, unicité, force du mot de passe,
    confirmation du mot de passe.
    """

    # Champ mot de passe — write_only = jamais renvoyé dans la réponse JSON
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],  # Vérifie la force du mot de passe
        style={'input_type': 'password'}
    )

    # Confirmation du mot de passe — uniquement pour la validation
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        label="Confirmer le mot de passe"
    )

    class Meta:
        model  = CustomUser
        fields = [
            'username', 'email',
            'nom', 'prenom', 'telephone',
            'password', 'password2'
        ]

    def validate_email(self, value):
        """
        Vérifie que l'email n'est pas déjà utilisé.
        Django vérifie l'unicité en DB mais ce message
        est plus clair pour l'utilisateur.
        """
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "Un compte existe déjà avec cette adresse email."
            )
        return value.lower()  # Stocke toujours en minuscules

    def validate(self, attrs):
        """
        Validation croisée — vérifie que les deux
        mots de passe sont identiques.
        """
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({
                'password': "Les deux mots de passe ne correspondent pas."
            })
        return attrs

    def create(self, validated_data):
        """
        Crée l'utilisateur après validation.
        On supprime password2 car il ne correspond à aucun champ du modèle.
        """
        # Retire le champ de confirmation avant la création
        validated_data.pop('password2')

        # Crée l'utilisateur avec le mot de passe hashé
        # is_active=False → le compte est inactif jusqu'à vérification email
        user = CustomUser.objects.create_user(
            **validated_data,
            is_active=False   # Activé après vérification email
        )
        return user


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Changement de mot de passe
# ═══════════════════════════════════════════════════════════════

class ChangerMotDePasseSerializer(serializers.Serializer):
    """
    Permet à un utilisateur connecté de changer son mot de passe.
    Vérifie l'ancien mot de passe avant d'accepter le nouveau.
    """

    ancien_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    nouveau_password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    nouveau_password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        label="Confirmer le nouveau mot de passe"
    )

    def validate_ancien_password(self, value):
        """Vérifie que l'ancien mot de passe est correct"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError(
                "L'ancien mot de passe est incorrect."
            )
        return value

    def validate(self, attrs):
        """Vérifie que les deux nouveaux mots de passe correspondent"""
        if attrs['nouveau_password'] != attrs['nouveau_password2']:
            raise serializers.ValidationError({
                'nouveau_password': "Les deux mots de passe ne correspondent pas."
            })
        return attrs

    def save(self, **kwargs):
        """Applique le nouveau mot de passe"""
        user = self.context['request'].user
        user.set_password(self.validated_data['nouveau_password'])
        user.save()
        return user


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Adresse de livraison
# ═══════════════════════════════════════════════════════════════

class AdresseLivraisonSerializer(serializers.ModelSerializer):
    """
    Gère l'affichage et la création des adresses de livraison.
    L'utilisateur est automatiquement associé via la vue (pas via le JSON).
    """

    class Meta:
        model  = AdresseLivraison
        fields = [
            'id', 'nom_complet', 'telephone',
            'adresse', 'ville', 'region',
            'pays', 'code_postal', 'is_default',
            'date_creation'
        ]
        read_only_fields = ['date_creation']

    def create(self, validated_data):
        """
        Associe automatiquement l'utilisateur connecté
        à l'adresse créée.
        """
        # L'utilisateur vient du contexte de la requête
        utilisateur = self.context['request'].user
        return AdresseLivraison.objects.create(
            utilisateur=utilisateur,
            **validated_data
        )