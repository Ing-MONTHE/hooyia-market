"""
HooYia Market — products/admin.py
Interface d'administration pour les produits, catégories et stocks.
"""
from django.contrib import admin
from django.utils.html import format_html
from mptt.admin import MPTTModelAdmin
from .models import Produit, Categorie, ImageProduit, MouvementStock


# ═══════════════════════════════════════════════════════════════
# INLINE — Images produit
# Affiche les images directement sur la page du produit
# ═══════════════════════════════════════════════════════════════

class ImageProduitInline(admin.TabularInline):
    model   = ImageProduit
    extra   = 1  # Un formulaire vide pour ajouter une image
    readonly_fields = ['apercu_image', 'date_ajout']
    fields  = ['image', 'apercu_image', 'alt_text', 'ordre', 'est_principale']

    def apercu_image(self, obj):
        """Miniature de l'image dans l'admin"""
        if obj.image:
            return format_html(
                '<img src="{}" width="80" height="80" '
                'style="object-fit:cover; border-radius:4px;" />',
                obj.image.url
            )
        return "Aucune image"
    apercu_image.short_description = "Aperçu"


# ═══════════════════════════════════════════════════════════════
# INLINE — Mouvements de stock
# Affiche l'historique du stock sur la page du produit
# ═══════════════════════════════════════════════════════════════

class MouvementStockInline(admin.TabularInline):
    model   = MouvementStock
    extra   = 0
    readonly_fields = ['stock_avant', 'stock_apres', 'date', 'effectue_par']
    fields  = ['type_mouvement', 'quantite', 'stock_avant', 'stock_apres', 'note', 'date']

    # Pas de modification des mouvements passés (traçabilité)
    def has_change_permission(self, request, obj=None):
        return False


# ═══════════════════════════════════════════════════════════════
# ADMIN — Catégorie
# Affichage en arbre grâce à MPTTModelAdmin
# ═══════════════════════════════════════════════════════════════

@admin.register(Categorie)
class CategorieAdmin(MPTTModelAdmin):

    list_display  = ['nom', 'parent', 'est_active', 'nombre_produits']
    list_filter   = ['est_active']
    search_fields = ['nom']
    prepopulated_fields = {'slug': ('nom',)}  # Slug auto depuis le nom
    readonly_fields = ['date_creation']

    def nombre_produits(self, obj):
        """Affiche le nombre de produits dans cette catégorie"""
        return obj.produits.count()
    nombre_produits.short_description = "Produits"


# ═══════════════════════════════════════════════════════════════
# ADMIN — Produit
# ═══════════════════════════════════════════════════════════════

@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):

    list_display  = [
        'nom', 'categorie', 'vendeur',
        'prix', 'prix_promo', 'stock',
        'statut', 'en_vedette',
        'note_moyenne', 'date_creation',
        'apercu_image_principale'
    ]
    list_filter   = ['statut', 'en_vedette', 'categorie']
    search_fields = ['nom', 'description', 'vendeur__username']
    prepopulated_fields = {'slug': ('nom',)}
    readonly_fields = [
        'date_creation', 'date_modification',
        'note_moyenne', 'nombre_avis'
    ]
    inlines = [ImageProduitInline, MouvementStockInline]

    # Organisation des champs
    fieldsets = (
        ('Informations générales', {
            'fields': ('nom', 'slug', 'description', 'description_courte')
        }),
        ('Prix', {
            'fields': ('prix', 'prix_promo')
        }),
        ('Stock', {
            'fields': ('stock', 'stock_minimum')
        }),
        ('Classification', {
            'fields': ('categorie', 'vendeur', 'statut', 'en_vedette')
        }),
        ('Statistiques', {
            'fields': ('note_moyenne', 'nombre_avis'),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )

    # ── Actions en masse ──────────────────────────────────────
    actions = [
        'activer_produits',
        'desactiver_produits',
        'mettre_en_vedette',
        'retirer_vedette',
        'exporter_csv'
    ]

    def activer_produits(self, request, queryset):
        nb = queryset.update(statut='actif')
        self.message_user(request, f"{nb} produit(s) activé(s).")
    activer_produits.short_description = "✅ Activer les produits sélectionnés"

    def desactiver_produits(self, request, queryset):
        nb = queryset.update(statut='inactif')
        self.message_user(request, f"{nb} produit(s) désactivé(s).")
    desactiver_produits.short_description = "🚫 Désactiver les produits sélectionnés"

    def mettre_en_vedette(self, request, queryset):
        nb = queryset.update(en_vedette=True)
        self.message_user(request, f"{nb} produit(s) mis en vedette.")
    mettre_en_vedette.short_description = "⭐ Mettre en vedette"

    def retirer_vedette(self, request, queryset):
        nb = queryset.update(en_vedette=False)
        self.message_user(request, f"{nb} produit(s) retirés de la vedette.")
    retirer_vedette.short_description = "☆ Retirer de la vedette"

    def exporter_csv(self, request, queryset):
        """Exporte les produits sélectionnés en CSV"""
        import csv
        from django.http import HttpResponse

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="produits.csv"'

        writer = csv.writer(response)
        # En-têtes
        writer.writerow(['ID', 'Nom', 'Prix', 'Stock', 'Statut', 'Catégorie'])
        # Données
        for p in queryset:
            writer.writerow([
                p.id, p.nom, p.prix,
                p.stock, p.statut,
                p.categorie.nom if p.categorie else ''
            ])
        return response
    exporter_csv.short_description = "📥 Exporter en CSV"

    def apercu_image_principale(self, obj):
        """Affiche la première image du produit dans la liste"""
        image = obj.images.filter(est_principale=True).first() or obj.images.first()
        if image:
            return format_html(
                '<img src="{}" width="50" height="50" '
                'style="object-fit:cover; border-radius:4px;" />',
                image.image.url
            )
        return "—"
    apercu_image_principale.short_description = "Image"


# ═══════════════════════════════════════════════════════════════
# ADMIN — Mouvement de stock
# ═══════════════════════════════════════════════════════════════

@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):

    list_display  = [
        'produit', 'type_mouvement', 'quantite',
        'stock_avant', 'stock_apres',
        'effectue_par', 'date'
    ]
    list_filter   = ['type_mouvement', 'date']
    search_fields = ['produit__nom', 'note']
    readonly_fields = ['date']

    # Les mouvements ne peuvent pas être modifiés (traçabilité)
    def has_change_permission(self, request, obj=None):
        return False