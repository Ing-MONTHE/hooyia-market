"""
HooYia Market — reviews/admin.py
Interface d'administration pour les avis clients.

Fonctionnalités :
  - Affichage coloré du statut de validation
  - Actions en masse : valider / invalider plusieurs avis
  - Filtres par note, statut de validation, produit
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Avis


@admin.register(Avis)
class AvisAdmin(admin.ModelAdmin):
    """
    Administration des avis clients.
    L'admin peut modérer les avis (valider/invalider) depuis cette interface.
    """

    # ── Colonnes affichées dans la liste ──────────────────────
    list_display = [
        'utilisateur',
        'produit',
        'note_etoiles',     # Affichage visuel avec ★
        'commentaire_court',
        'statut_badge',     # Badge coloré vert/rouge
        'date_creation',
    ]

    # ── Filtres latéraux ──────────────────────────────────────
    list_filter = [
        'is_validated',        # Avis validés / en attente
        'note',             # Filtrer par note (1, 2, 3, 4, 5)
        'date_creation',
    ]

    # ── Recherche ─────────────────────────────────────────────
    search_fields = [
        'utilisateur__username',
        'utilisateur__email',
        'produit__nom',
        'commentaire',
    ]

    # ── Tri par défaut : les plus récents d'abord ─────────────
    ordering = ['-date_creation']

    # ── Champs non modifiables ────────────────────────────────
    readonly_fields = ['date_creation', 'date_modification']

    # ── Actions en masse ──────────────────────────────────────
    actions = ['valider_avis_selectionnes', 'invalider_avis_selectionnes']

    # ── Méthodes d'affichage personnalisées ───────────────────

    def note_etoiles(self, obj):
        """Affiche la note sous forme d'étoiles (ex: ★★★☆☆ pour 3/5)"""
        etoiles_pleines = '★' * obj.note
        etoiles_vides   = '☆' * (5 - obj.note)
        return format_html(
            '<span style="color: #f59e0b; font-size: 16px;">{}{}</span>',
            etoiles_pleines,
            etoiles_vides
        )
    note_etoiles.short_description = "Note"

    def commentaire_court(self, obj):
        """Tronque le commentaire à 60 caractères pour la liste"""
        if not obj.commentaire:
            return "—"
        if len(obj.commentaire) > 60:
            return obj.commentaire[:60] + "…"
        return obj.commentaire
    commentaire_court.short_description = "Commentaire"

    def statut_badge(self, obj):
        """Badge coloré : vert si validé, orange si en attente"""
        if obj.is_validated:
            return format_html(
                '<span style="background:#16a34a; color:white; padding:2px 8px; '
                'border-radius:4px; font-size:11px;">✓ Validé</span>'
            )
        return format_html(
            '<span style="background:#d97706; color:white; padding:2px 8px; '
            'border-radius:4px; font-size:11px;">⏳ En attente</span>'
        )
    statut_badge.short_description = "Statut"

    # ── Actions en masse ──────────────────────────────────────

    def valider_avis_selectionnes(self, request, queryset):
        """
        Valide tous les avis sélectionnés en une seule opération.
        Attention : update() en masse ne déclenche pas les signals post_save.
        On utilise donc une boucle pour que chaque signal soit bien déclenché
        et que la note_moyenne de chaque produit soit recalculée.
        """
        count = 0
        for avis in queryset.filter(is_validated=False):
            avis.is_validated = True
            avis.save(update_fields=['is_validated'])  # Déclenche le signal
            count += 1
        self.message_user(request, f"{count} avis validé(s). Les notes moyennes ont été recalculées.")
    valider_avis_selectionnes.short_description = "✓ Valider les avis sélectionnés"

    def invalider_avis_selectionnes(self, request, queryset):
        """
        Invalide les avis sélectionnés (modération).
        Même logique que valider : boucle pour déclencher les signals.
        """
        count = 0
        for avis in queryset.filter(is_validated=True):
            avis.is_validated = False
            avis.save(update_fields=['is_validated'])  # Déclenche le signal
            count += 1
        self.message_user(request, f"{count} avis invalidé(s). Les notes moyennes ont été recalculées.")
    invalider_avis_selectionnes.short_description = "✗ Invalider les avis sélectionnés"