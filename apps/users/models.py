"""
HooYia Market — users/models.py
Gestion des utilisateurs, adresses de livraison et rôles.

On remplace le modèle User par défaut de Django par notre propre modèle
CustomUser pour avoir un contrôle total sur les champs et comportements.
"""
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone


# ═══════════════════════════════════════════════════════════════
# MANAGER UTILISATEUR
# Le "manager" est le chef d'orchestre qui sait comment créer
# un utilisateur. On le personnalise car on utilise l'email
# comme identifiant principal au lieu du username.
# ═══════════════════════════════════════════════════════════════

class CustomUserManager(BaseUserManager):

    def create_user(self, email, username, password=None, **extra_fields):
        """
        Crée un utilisateur normal.
        Appelé lors de l'inscription classique.
        """
        if not email:
            raise ValueError("L'adresse email est obligatoire")
        if not username:
            raise ValueError("Le nom d'utilisateur est obligatoire")

        # Normalise l'email (met le domaine en minuscules)
        email = self.normalize_email(email)

        user = self.model(email=email, username=username, **extra_fields)

        # hash le mot de passe avant de le stocker (jamais en clair)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        """
        Crée un administrateur (accès total).
        Appelé via : python manage.py createsuperuser
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_admin', True)

        return self.create_user(email, username, password, **extra_fields)


# ═══════════════════════════════════════════════════════════════
# MODÈLE UTILISATEUR PERSONNALISÉ
# AbstractBaseUser = modèle de base Django sans les champs
# par défaut (on définit tout nous-mêmes)
# PermissionsMixin = ajoute la gestion des permissions Django
# ═══════════════════════════════════════════════════════════════

class CustomUser(AbstractBaseUser, PermissionsMixin):

    # ── Informations de base ──────────────────────────────────
    username = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Nom d'utilisateur"
    )
    email = models.EmailField(
        unique=True,
        verbose_name="Adresse email"
    )
    nom = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Nom"
    )
    prenom = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Prénom"
    )
    telephone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Téléphone"
    )
    photo_profil = models.ImageField(
        upload_to='profils/',
        null=True,
        blank=True,
        verbose_name="Photo de profil"
    )

    # ── Statuts du compte ─────────────────────────────────────
    is_active = models.BooleanField(
        default=False,           # False = compte non activé par email
        verbose_name="Compte actif"
    )
    is_staff = models.BooleanField(
        default=False,           # Accès à l'admin Django
        verbose_name="Staff"
    )
    is_admin = models.BooleanField(
        default=False,           # Administrateur HooYia Market
        verbose_name="Administrateur"
    )
    is_vendeur = models.BooleanField(
        default=False,           # Peut créer et gérer des produits
        verbose_name="Vendeur"
    )
    email_verifie = models.BooleanField(
        default=False,           # True après clic sur le lien de vérification
        verbose_name="Email vérifié"
    )

    # ── Dates ─────────────────────────────────────────────────
    date_inscription = models.DateTimeField(
        default=timezone.now,
        verbose_name="Date d'inscription"
    )
    derniere_connexion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Dernière connexion"
    )

    # ── Configuration du manager ──────────────────────────────
    objects = CustomUserManager()

    # On utilise l'email comme identifiant de connexion
    USERNAME_FIELD = 'email'

    # Champs demandés lors de createsuperuser (en plus de email + password)
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ['-date_inscription']

    def __str__(self):
        return f"{self.username} ({self.email})"

    def get_full_name(self):
        """Retourne le nom complet de l'utilisateur"""
        return f"{self.prenom} {self.nom}".strip() or self.username

    def get_short_name(self):
        """Retourne uniquement le prénom"""
        return self.prenom or self.username


# ═══════════════════════════════════════════════════════════════
# ADRESSE DE LIVRAISON
# Un utilisateur peut avoir plusieurs adresses enregistrées.
# Une seule peut être "par défaut" à la fois.
# ═══════════════════════════════════════════════════════════════

class AdresseLivraison(models.Model):

    # L'utilisateur propriétaire de cette adresse
    utilisateur = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='adresses',
        verbose_name="Utilisateur"
    )

    # ── Champs de l'adresse ───────────────────────────────────
    nom_complet     = models.CharField(max_length=150, verbose_name="Nom complet")
    telephone       = models.CharField(max_length=20,  verbose_name="Téléphone")
    adresse         = models.CharField(max_length=255, verbose_name="Adresse")
    ville           = models.CharField(max_length=100, verbose_name="Ville")
    region          = models.CharField(max_length=100, verbose_name="Région")
    pays            = models.CharField(max_length=100, default="Cameroun", verbose_name="Pays")
    code_postal     = models.CharField(max_length=10,  blank=True, verbose_name="Code postal")

    # Adresse utilisée par défaut lors du passage de commande
    is_default = models.BooleanField(default=False, verbose_name="Adresse par défaut")

    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Adresse de livraison"
        verbose_name_plural = "Adresses de livraison"
        ordering = ['-is_default', '-date_creation']

    def __str__(self):
        return f"{self.nom_complet} — {self.ville}, {self.pays}"

    def save(self, *args, **kwargs):
        """
        Si cette adresse est marquée comme défaut,
        on retire le statut 'défaut' de toutes les autres
        adresses de cet utilisateur.
        """
        if self.is_default:
            AdresseLivraison.objects.filter(
                utilisateur=self.utilisateur,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)

        super().save(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════
# TOKEN DE VÉRIFICATION EMAIL
# Quand un utilisateur s'inscrit, on génère un token unique
# qu'on envoie par email. En cliquant sur le lien, son compte
# est activé.
# ═══════════════════════════════════════════════════════════════

import uuid

class TokenVerificationEmail(models.Model):

    utilisateur = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='token_verification'
    )

    # Token unique généré automatiquement
    token = models.UUIDField(default=uuid.uuid4, unique=True)

    # Date de création (le token expire après 24h)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Token de {self.utilisateur.email}"

    def est_expire(self):
        """Vérifie si le token a plus de 24h"""
        from datetime import timedelta
        return timezone.now() > self.date_creation + timedelta(hours=24)