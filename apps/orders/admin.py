"""
Interface d'administration pour les commandes, lignes et paiements.
Permet aux admins de suivre et gérer les commandes directement depuis l'admin.
"""
from django.contrib import admin
from django.utils.html import format_html
from django_fsm import TransitionNotAllowed
from .models import Commande, LigneCommande, Paiement


# ═══════════════════════════════════════════════════════════════
# INLINE — Lignes de commande
# Affiche les articles commandés sur la page de la commande
# ═══════════════════════════════════════════════════════════════

class LigneCommandeInline(admin.TabularInline):
    model   = LigneCommande
    extra   = 0
    readonly_fields = [
        'produit', 'produit_nom', 'quantite',
        'prix_unitaire', 'sous_total_affiche'
    ]
    fields  = [
        'produit', 'produit_nom', 'quantite',
        'prix_unitaire', 'sous_total_affiche'
    ]

    # Les lignes de commande ne se modifient pas
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def sous_total_affiche(self, obj):
        return f"{obj.sous_total:,.0f} FCFA"
    sous_total_affiche.short_description = "Sous-total"


# ═══════════════════════════════════════════════════════════════
# INLINE — Paiement
# Affiche les infos de paiement sur la page de la commande
# ═══════════════════════════════════════════════════════════════

class PaiementInline(admin.StackedInline):
    model   = Paiement
    extra   = 0
    readonly_fields = ['montant', 'date_paiement']
    fields  = ['mode', 'statut', 'montant', 'reference_externe', 'date_paiement']

    def has_add_permission(self, request, obj=None):
        return False


# ═══════════════════════════════════════════════════════════════
# ADMIN — Commande
# ═══════════════════════════════════════════════════════════════

@admin.register(Commande)
class CommandeAdmin(admin.ModelAdmin):

    list_display  = [
        'reference_courte_affiche', 'client',
        'statut_badge', 'montant_total_affiche',
        'adresse_livraison_ville', 'date_creation'
    ]
    list_filter   = ['statut', 'date_creation']
    search_fields = [
        'reference', 'client__username', 'client__email',
        'adresse_livraison_nom', 'adresse_livraison_ville'
    ]
    readonly_fields = [
        'reference', 'reference_courte_affiche',
        'date_creation', 'date_modification', 'date_livraison'
    ]
    inlines = [LigneCommandeInline, PaiementInline]

    # ── Actions FSM en masse ──────────────────────────────────
    actions = [
        'action_confirmer',
        'action_mettre_en_preparation',
        'action_expedier',
        'action_livrer',
        'action_annuler',
    ]

    def reference_courte_affiche(self, obj):
        return f"#{obj.reference_courte}"
    reference_courte_affiche.short_description = "Référence"

    def montant_total_affiche(self, obj):
        return f"{obj.montant_total:,.0f} FCFA"
    montant_total_affiche.short_description = "Total"

    def statut_badge(self, obj):
        """Affiche le statut avec une couleur selon l'état"""
        couleurs = {
            'en_attente'     : '#f59e0b',  # orange
            'confirmee'      : '#3b82f6',  # bleu
            'en_preparation' : '#8b5cf6',  # violet
            'expediee'       : '#06b6d4',  # cyan
            'livree'         : '#10b981',  # vert
            'annulee'        : '#ef4444',  # rouge
        }
        couleur = couleurs.get(obj.statut, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:3px 8px;'
            'border-radius:4px;font-size:11px;">{}</span>',
            couleur, obj.get_statut_display()
        )
    statut_badge.short_description = "Statut"

    # ── Actions FSM ───────────────────────────────────────────

    def _appliquer_transition(self, request, queryset, methode, message):
        """Applique une transition FSM à un ensemble de commandes"""
        succes = 0
        for commande in queryset:
            try:
                getattr(commande, methode)()
                commande.save()
                succes += 1
            except TransitionNotAllowed:
                pass  # On ignore les commandes qui ne peuvent pas transitionner
        self.message_user(request, f"{succes} commande(s) mise(s) à jour : {message}.")

    def action_confirmer(self, request, queryset):
        self._appliquer_transition(request, queryset, 'confirmer', 'Confirmée')
    action_confirmer.short_description = "✅ Confirmer les commandes"

    def action_mettre_en_preparation(self, request, queryset):
        self._appliquer_transition(request, queryset, 'mettre_en_preparation', 'En préparation')
    action_mettre_en_preparation.short_description = "📦 Mettre en préparation"

    def action_expedier(self, request, queryset):
        self._appliquer_transition(request, queryset, 'expedier', 'Expédiée')
    action_expedier.short_description = "🚚 Marquer comme expédiée"

    def action_livrer(self, request, queryset):
        self._appliquer_transition(request, queryset, 'livrer', 'Livrée')
    action_livrer.short_description = "🏠 Marquer comme livrée"

    def action_annuler(self, request, queryset):
        self._appliquer_transition(request, queryset, 'annuler', 'Annulée')
    action_annuler.short_description = "❌ Annuler les commandes"