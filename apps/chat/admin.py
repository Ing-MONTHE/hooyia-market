"""
Interface d'administration pour le chat.

Fonctionnalités :
  - Visualisation des conversations et de leurs messages
  - Filtre par participant, date
  - Inline messages dans la conversation
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import Conversation, MessageChat


# ── Inline : messages dans une conversation ───────────────────
class MessageChatInline(admin.TabularInline):
    """
    Affiche les messages directement dans la page d'une conversation.
    Lecture seule : on ne modifie pas les messages depuis l'admin.
    """
    model          = MessageChat
    extra          = 0             # Pas de formulaires vides
    readonly_fields = ['expediteur', 'contenu', 'is_read', 'date_envoi']
    can_delete     = False         # On ne supprime pas les messages depuis l'admin
    ordering       = ['date_envoi']
    max_num        = 50            # Limite l'affichage à 50 messages


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """
    Administration des conversations.
    Permet de visualiser les échanges entre utilisateurs.
    """

    list_display  = ['id', 'participant1', 'participant2', 'nombre_messages', 'date_creation']
    list_filter   = ['date_creation']
    search_fields = ['participant1__username', 'participant2__username', 'participant1__email']
    readonly_fields = ['date_creation']
    inlines        = [MessageChatInline]
    ordering       = ['-date_creation']

    def nombre_messages(self, obj):
        """Affiche le nombre de messages dans la conversation."""
        return obj.messages.count()
    nombre_messages.short_description = "Nb messages"


@admin.register(MessageChat)
class MessageChatAdmin(admin.ModelAdmin):
    """
    Administration des messages individuels.
    Utile pour la modération de contenu.
    """

    list_display  = ['id', 'expediteur', 'conversation', 'apercu_contenu', 'statut_lu', 'date_envoi']
    list_filter   = ['is_read', 'date_envoi']
    search_fields = ['expediteur__username', 'contenu']
    readonly_fields = ['conversation', 'expediteur', 'contenu', 'date_envoi']
    ordering       = ['-date_envoi']

    def apercu_contenu(self, obj):
        """Tronque le contenu à 60 caractères pour la liste."""
        if len(obj.contenu) > 60:
            return obj.contenu[:60] + "…"
        return obj.contenu
    apercu_contenu.short_description = "Message"

    def statut_lu(self, obj):
        """Badge coloré : vert si lu, orange si non lu."""
        if obj.is_read:
            return format_html(
                '<span style="background:#16a34a; color:white; padding:2px 8px; '
                'border-radius:4px; font-size:11px;">✓ Lu</span>'
            )
        return format_html(
            '<span style="background:#d97706; color:white; padding:2px 8px; '
            'border-radius:4px; font-size:11px;">● Non lu</span>'
        )
    statut_lu.short_description = "Statut"