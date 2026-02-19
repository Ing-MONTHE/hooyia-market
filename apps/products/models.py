"""
Gestion du catalogue produits :
- Categorie  : arbre hiérarchique (Électronique → Téléphones → Samsung)
- Produit    : fiche complète du produit
- ImageProduit : images multiples par produit
- MouvementStock : historique des entrées/sorties de stock
"""
from django.db import models
from django.utils.text import slugify
from django.conf import settings
from django.core.validators import MinValueValidator
from mptt.models import MPTTModel, TreeForeignKey
import uuid
from .managers import ProduitActifManager, ProduitEnVedetteManager, ProduitStockFaibleManager


# ═══════════════════════════════════════════════════════════════
# CATÉGORIE — Arbre hiérarchique via django-mptt
# Exemple : Électronique → Téléphones → Samsung
# ═══════════════════════════════════════════════════════════════

class Categorie(MPTTModel):
    """
    MPTTModel = Modified Preorder Tree Traversal
    Permet de gérer des catégories imbriquées efficacement.
    Une catégorie peut avoir un parent (sous-catégorie)
    ou être une catégorie racine (parent=None).
    """

    nom = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nom"
    )

    # Slug = version URL de nom (ex: "téléphones-samsung")
    slug = models.SlugField(
        max_length=120,
        unique=True,
        blank=True
    )

    description = models.TextField(
        blank=True,
        verbose_name="Description"
    )

    image = models.ImageField(
        upload_to='categories/',
        null=True,
        blank=True,
        verbose_name="Image"
    )

    # Catégorie parente (None = catégorie racine)
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sous_categories',
        verbose_name="Catégorie parente"
    )

    est_active = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class MPTTMeta:
        # Tri alphabétique dans l'arbre
        order_insertion_by = ['nom']

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        """Génère automatiquement le slug depuis le nom"""
        if not self.slug:
            self.slug = slugify(self.nom)
        super().save(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════
# PRODUIT
# ═══════════════════════════════════════════════════════════════

class Produit(models.Model):
    """
    Modèle principal du catalogue.
    Contient toutes les informations d'un produit.
    """

    # ── Statuts possibles d'un produit ───────────────────────
    class Statut(models.TextChoices):
        ACTIF     = 'actif',     'Actif'
        INACTIF   = 'inactif',   'Inactif'
        EPUISE    = 'epuise',    'Épuisé'
        ARCHIVE   = 'archive',   'Archivé'

    # ── Informations de base ──────────────────────────────────
    nom = models.CharField(
        max_length=255,
        verbose_name="Nom du produit"
    )

    slug = models.SlugField(
        max_length=280,
        unique=True,
        blank=True,
        verbose_name="Slug URL"
    )

    description = models.TextField(
        verbose_name="Description"
    )

    description_courte = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Description courte"
    )

    # ── Prix ──────────────────────────────────────────────────
    prix = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Prix (FCFA)"
    )

    prix_promo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name="Prix promotionnel (FCFA)"
    )

    # ── Stock ─────────────────────────────────────────────────
    stock = models.PositiveIntegerField(
        default=0,
        verbose_name="Quantité en stock"
    )

    stock_minimum = models.PositiveIntegerField(
        default=5,
        verbose_name="Seuil d'alerte stock"
    )

    # ── Relations ─────────────────────────────────────────────
    categorie = models.ForeignKey(
        Categorie,
        on_delete=models.SET_NULL,
        null=True,
        related_name='produits',
        verbose_name="Catégorie"
    )

    # Le vendeur qui a créé ce produit
    vendeur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='produits',
        verbose_name="Vendeur"
    )

    # ── Statut & Mise en avant ────────────────────────────────
    statut = models.CharField(
        max_length=10,
        choices=Statut.choices,
        default=Statut.ACTIF,
        verbose_name="Statut"
    )

    en_vedette = models.BooleanField(
        default=False,
        verbose_name="Produit en vedette"
    )

    # ── Note moyenne (calculée automatiquement par signal) ────
    note_moyenne = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        verbose_name="Note moyenne"
    )

    nombre_avis = models.PositiveIntegerField(
        default=0,
        verbose_name="Nombre d'avis"
    )

    # ── Managers ──────────────────────────────────────────────
    objects   = models.Manager()          # Manager par défaut (tous les produits)
    actifs    = ProduitActifManager()     # Produit.actifs.all()
    vedette   = ProduitEnVedetteManager() # Produit.vedette.all()
    stock_bas = ProduitStockFaibleManager() # Produit.stock_bas.all()

    # ── Dates ─────────────────────────────────────────────────
    date_creation    = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Produit"
        verbose_name_plural = "Produits"
        ordering = ['-date_creation']

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        """Génère automatiquement le slug depuis le nom"""
        if not self.slug:
            base_slug = slugify(self.nom)
            # Ajoute un identifiant unique si le slug existe déjà
            slug = base_slug
            counter = 1
            while Produit.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug

        # Met à jour le statut automatiquement si stock = 0
        if self.stock == 0 and self.statut == self.Statut.ACTIF:
            self.statut = self.Statut.EPUISE

        super().save(*args, **kwargs)

    @property
    def prix_actuel(self):
        """Retourne le prix promo s'il existe, sinon le prix normal"""
        return self.prix_promo if self.prix_promo else self.prix

    @property
    def est_en_stock(self):
        """Vérifie si le produit est disponible"""
        return self.stock > 0

    @property
    def stock_faible(self):
        """Vérifie si le stock est sous le seuil d'alerte"""
        return self.stock <= self.stock_minimum

    @property
    def pourcentage_remise(self):
        """Calcule le pourcentage de réduction si prix promo"""
        if self.prix_promo and self.prix > 0:
            remise = ((self.prix - self.prix_promo) / self.prix) * 100
            return round(remise)
        return 0


# ═══════════════════════════════════════════════════════════════
# IMAGE PRODUIT
# Chaque produit peut avoir plusieurs images.
# ═══════════════════════════════════════════════════════════════

class ImageProduit(models.Model):
    """
    Images multiples pour un produit.
    Le resize automatique est géré dans signals.py via Pillow.
    """

    produit = models.ForeignKey(
        Produit,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name="Produit"
    )

    image = models.ImageField(
        upload_to='products/',
        verbose_name="Image"
    )

    # Texte alternatif pour l'accessibilité
    alt_text = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Texte alternatif"
    )

    # Ordre d'affichage (0 = image principale)
    ordre = models.PositiveIntegerField(
        default=0,
        verbose_name="Ordre d'affichage"
    )

    est_principale = models.BooleanField(
        default=False,
        verbose_name="Image principale"
    )

    date_ajout = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Image produit"
        verbose_name_plural = "Images produit"
        ordering = ['ordre']

    def __str__(self):
        return f"Image {self.ordre} — {self.produit.nom}"

    def save(self, *args, **kwargs):
        """
        Si cette image est marquée comme principale,
        retire ce statut des autres images du même produit.
        """
        if self.est_principale:
            ImageProduit.objects.filter(
                produit=self.produit,
                est_principale=True
            ).exclude(pk=self.pk).update(est_principale=False)
        super().save(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════
# MOUVEMENT DE STOCK
# Historique de toutes les entrées et sorties de stock.
# ═══════════════════════════════════════════════════════════════

class MouvementStock(models.Model):
    """
    Enregistre chaque changement de stock.
    Entrée = réapprovisionnement
    Sortie = vente ou ajustement
    """

    class TypeMouvement(models.TextChoices):
        ENTREE     = 'entree',     'Entrée stock'
        SORTIE     = 'sortie',     'Sortie stock'
        AJUSTEMENT = 'ajustement', 'Ajustement'
        RETOUR     = 'retour',     'Retour client'

    produit = models.ForeignKey(
        Produit,
        on_delete=models.CASCADE,
        related_name='mouvements_stock',
        verbose_name="Produit"
    )

    type_mouvement = models.CharField(
        max_length=15,
        choices=TypeMouvement.choices,
        verbose_name="Type"
    )

    quantite = models.IntegerField(
        verbose_name="Quantité"
    )

    # Stock avant et après le mouvement (pour traçabilité)
    stock_avant  = models.PositiveIntegerField(verbose_name="Stock avant")
    stock_apres  = models.PositiveIntegerField(verbose_name="Stock après")

    note = models.TextField(
        blank=True,
        verbose_name="Note"
    )

    # Qui a effectué ce mouvement
    effectue_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Effectué par"
    )

    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mouvement de stock"
        verbose_name_plural = "Mouvements de stock"
        ordering = ['-date']

    def __str__(self):
        return f"{self.type_mouvement} | {self.produit.nom} | {self.quantite}"