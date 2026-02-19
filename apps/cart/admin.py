"""
HooYia Market — cart/admin.py
Interface d'administration pour les paniers et leurs articles.
Utile pour déboguer, voir l'état des paniers clients et
surveiller les articles abandonnés.
"""
from django.contrib import admin
from .models import Panier, PanierItem


# ═══════════════════════════════════════════════════════════════
# INLINE — Articles du panier
# Affiche les lignes directement sur la page du panier dans l'admin
# ═══════════════════════════════════════════════════════════════

class PanierItemInline(admin.TabularInline):
    model   = PanierItem
    extra   = 0    # Pas de formulaire vide (on ne crée pas de ligne depuis l'admin)
    readonly_fields = [
        'produit', 'quantite', 'prix_snapshot',
        'sous_total_affiche', 'date_ajout'
    ]
    fields  = [
        'produit', 'quantite', 'prix_snapshot',
        'sous_total_affiche', 'date_ajout'
    ]

    # Les paniers clients ne se modifient pas depuis l'admin
    def has_add_permission(self, request, obj=None):
        return False

    def sous_total_affiche(self, obj):
        """Calcule et affiche le sous-total de la ligne"""
        return f"{obj.sous_total:,.0f} FCFA"
    sous_total_affiche.short_description = "Sous-total"


# ═══════════════════════════════════════════════════════════════
# ADMIN — Panier
# ═══════════════════════════════════════════════════════════════

@admin.register(Panier)
class PanierAdmin(admin.ModelAdmin):

    list_display  = [
        'utilisateur', 'nombre_articles_affiche',
        'total_affiche', 'date_modification'
    ]
    search_fields = ['utilisateur__username', 'utilisateur__email']
    readonly_fields = ['date_creation', 'date_modification']
    inlines = [PanierItemInline]

    def nombre_articles_affiche(self, obj):
        """Affiche le nombre total d'articles dans le panier"""
        return obj.nombre_articles
    nombre_articles_affiche.short_description = "Nb articles"

    def total_affiche(self, obj):
        """Affiche le total du panier formaté"""
        return f"{obj.total:,.0f} FCFA"
    total_affiche.short_description = "Total"