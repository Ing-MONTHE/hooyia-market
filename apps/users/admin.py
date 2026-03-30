"""
Configure l'affichage et la gestion des utilisateurs
dans l'interface d'administration Django.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import CustomUser, AdresseLivraison, TokenVerificationEmail


# ═══════════════════════════════════════════════════════════════
# INLINE — Adresses de livraison
# Permet de voir et modifier les adresses directement
# depuis la page d'un utilisateur dans l'admin
# ═══════════════════════════════════════════════════════════════


class AdresseLivraisonInline(admin.TabularInline):
    model = AdresseLivraison
    # Nombre de formulaires vides affichés pour ajouter une adresse
    extra = 0
    readonly_fields = ["date_creation"]


# ═══════════════════════════════════════════════════════════════
# ADMIN UTILISATEUR
# On hérite de UserAdmin (admin Django par défaut)
# et on l'adapte à notre CustomUser
# ═══════════════════════════════════════════════════════════════


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):

    # ── Colonnes affichées dans la liste des utilisateurs ─────
    list_display = [
        "username",
        "email",
        "get_full_name",
        "is_active",
        "is_vendeur",
        "is_admin",
        "email_verifie",
        "date_inscription",
        "afficher_photo",
    ]

    # ── Filtres dans la barre latérale droite ─────────────────
    list_filter = [
        "is_active",
        "is_admin",
        "is_vendeur",
        "email_verifie",
        "date_inscription",
    ]

    # ── Champs de recherche ───────────────────────────────────
    search_fields = ["username", "email", "nom", "prenom"]

    # ── Ordre d'affichage ─────────────────────────────────────
    ordering = ["-date_inscription"]

    # ── Adresses affichées directement sur la page user ───────
    inlines = [AdresseLivraisonInline]

    # ── Champs en lecture seule ───────────────────────────────
    readonly_fields = ["date_inscription", "derniere_connexion", "afficher_photo"]

    # ── Organisation des champs dans le formulaire d'édition ──
    fieldsets = (
        # Section 1 : Informations de connexion
        ("Connexion", {"fields": ("email", "username", "password")}),
        # Section 2 : Informations personnelles
        (
            "Informations personnelles",
            {
                "fields": (
                    "nom",
                    "prenom",
                    "telephone",
                    "photo_profil",
                    "afficher_photo",
                )
            },
        ),
        # Section 3 : Statuts et permissions
        (
            "Statuts",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_admin",
                    "is_vendeur",
                    "email_verifie",
                )
            },
        ),
        # Section 4 : Permissions Django (groupes, etc.)
        (
            "Permissions",
            {
                "fields": ("groups", "user_permissions"),
                "classes": ("collapse",),  # Section repliée par défaut
            },
        ),
        # Section 5 : Dates (lecture seule)
        (
            "Dates",
            {
                "fields": ("date_inscription", "derniere_connexion"),
                "classes": ("collapse",),
            },
        ),
    )

    # ── Formulaire de création d'un nouvel utilisateur ────────
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "username",
                    "nom",
                    "prenom",
                    "password1",
                    "password2",
                    "is_active",
                    "is_vendeur",
                ),
            },
        ),
    )

    # ── Actions en masse ──────────────────────────────────────
    actions = ["activer_comptes", "desactiver_comptes", "promouvoir_vendeur"]

    def activer_comptes(self, request, queryset):
        """Active tous les comptes sélectionnés"""
        nb = queryset.update(is_active=True, email_verifie=True)
        self.message_user(request, f"{nb} compte(s) activé(s) avec succès.")

    activer_comptes.short_description = "✅ Activer les comptes sélectionnés"

    def desactiver_comptes(self, request, queryset):
        """Désactive tous les comptes sélectionnés"""
        nb = queryset.update(is_active=False)
        self.message_user(request, f"{nb} compte(s) désactivé(s).")

    desactiver_comptes.short_description = "🚫 Désactiver les comptes sélectionnés"

    def promouvoir_vendeur(self, request, queryset):
        """Donne le statut vendeur aux utilisateurs sélectionnés"""
        nb = queryset.update(is_vendeur=True)
        self.message_user(request, f"{nb} utilisateur(s) promu(s) vendeur.")

    promouvoir_vendeur.short_description = "🏪 Promouvoir en vendeur"

    def afficher_photo(self, obj):
        """Affiche la photo de profil en miniature dans l'admin"""
        if obj.photo_profil:
            return format_html(
                '<img src="{}" width="50" height="50" '
                'style="border-radius:50%; object-fit:cover;" />',
                obj.photo_profil.url,
            )
        return "Aucune photo"

    afficher_photo.short_description = "Photo"


# ═══════════════════════════════════════════════════════════════
# ADMIN ADRESSE DE LIVRAISON
# ═══════════════════════════════════════════════════════════════


@admin.register(AdresseLivraison)
class AdresseLivraisonAdmin(admin.ModelAdmin):

    list_display = ["nom_complet", "utilisateur", "ville", "pays", "is_default"]
    list_filter = ["pays", "ville", "is_default"]
    search_fields = ["nom_complet", "utilisateur__email", "ville"]
    readonly_fields = ["date_creation"]


# ═══════════════════════════════════════════════════════════════
# ADMIN TOKEN VÉRIFICATION EMAIL
# ═══════════════════════════════════════════════════════════════


@admin.register(TokenVerificationEmail)
class TokenVerificationEmailAdmin(admin.ModelAdmin):

    list_display = ["utilisateur", "token", "date_creation", "est_expire"]
    readonly_fields = ["token", "date_creation"]
    search_fields = ["utilisateur__email"]

    def est_expire(self, obj):
        """Affiche si le token est encore valide"""
        if obj.est_expire():
            return format_html('<span style="color:red;">❌ Expiré</span>')
        return format_html('<span style="color:green;">✅ Valide</span>')

    est_expire.short_description = "Statut token"
