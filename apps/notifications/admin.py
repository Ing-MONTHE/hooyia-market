"""
Interface d'administration pour les notifications et emails asynchrones.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Notification, EmailAsynchrone


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Administration des notifications in-app."""

    list_display  = ['utilisateur', 'titre', 'type_badge', 'statut_badge', 'date_creation']
    list_filter   = ['type_notif', 'is_read', 'date_creation']
    search_fields = ['utilisateur__username', 'titre', 'message']
    readonly_fields = ['date_creation']
    ordering      = ['-date_creation']
    actions       = ['marquer_lues', 'marquer_non_lues']

    def type_badge(self, obj):
        """Badge coloré par type de notification."""
        couleurs = {
            'commande': '#2563eb',
            'avis'    : '#16a34a',
            'stock'   : '#d97706',
            'systeme' : '#6b7280',
        }
        couleur = couleurs.get(obj.type_notif, '#6b7280')
        return format_html(
            '<span style="background:{}; color:white; padding:2px 8px; '
            'border-radius:4px; font-size:11px;">{}</span>',
            couleur, obj.get_type_notif_display()
        )
    type_badge.short_description = "Type"

    def statut_badge(self, obj):
        """Badge vert si lue, orange si non lue."""
        if obj.is_read:
            return format_html(
                '<span style="background:#16a34a; color:white; padding:2px 8px; '
                'border-radius:4px; font-size:11px;">✓ Lue</span>'
            )
        return format_html(
            '<span style="background:#d97706; color:white; padding:2px 8px; '
            'border-radius:4px; font-size:11px;">● Non lue</span>'
        )
    statut_badge.short_description = "Statut"

    def marquer_lues(self, request, queryset):
        """Marque les notifications sélectionnées comme lues."""
        updated = queryset.filter(is_read=False).update(is_read=True)
        self.message_user(request, f"{updated} notification(s) marquée(s) comme lue(s).")
    marquer_lues.short_description = "✓ Marquer comme lues"

    def marquer_non_lues(self, request, queryset):
        """Marque les notifications sélectionnées comme non lues."""
        updated = queryset.filter(is_read=True).update(is_read=False)
        self.message_user(request, f"{updated} notification(s) marquée(s) comme non lue(s).")
    marquer_non_lues.short_description = "● Marquer comme non lues"


@admin.register(EmailAsynchrone)
class EmailAsynchroneAdmin(admin.ModelAdmin):
    """Administration des emails envoyés par Celery (log + débogage)."""

    list_display  = ['destinataire', 'sujet', 'statut_badge', 'date_creation', 'date_envoi']
    list_filter   = ['statut', 'date_creation']
    search_fields = ['destinataire__username', 'sujet', 'email_destinataire']
    readonly_fields = ['destinataire', 'sujet', 'corps', 'email_destinataire',
                       'statut', 'erreur', 'date_creation', 'date_envoi']
    ordering      = ['-date_creation']

    def statut_badge(self, obj):
        """Badge coloré selon le statut d'envoi."""
        styles = {
            'en_attente': ('#d97706', '⏳ En attente'),
            'envoye'    : ('#16a34a', '✓ Envoyé'),
            'echec'     : ('#dc2626', '✗ Échec'),
        }
        couleur, label = styles.get(obj.statut, ('#6b7280', obj.statut))
        return format_html(
            '<span style="background:{}; color:white; padding:2px 8px; '
            'border-radius:4px; font-size:11px;">{}</span>',
            couleur, label
        )
    statut_badge.short_description = "Statut"