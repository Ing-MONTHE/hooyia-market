"""
HooYia Market — users/permissions.py
Permissions personnalisées pour l'API DRF.
Utilisées pour contrôler qui peut faire quoi.
"""
from rest_framework.permissions import BasePermission


class EstAdminOuLectureSeule(BasePermission):
    """
    - Tout le monde peut lire (GET)
    - Seuls les admins peuvent écrire (POST, PUT, DELETE)
    """
    def has_permission(self, request, view):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        return request.user and request.user.is_admin


class EstProprietaire(BasePermission):
    """
    Vérifie que l'utilisateur est le propriétaire de l'objet.
    Ex: un utilisateur ne peut modifier QUE son propre profil.
    """
    def has_object_permission(self, request, view, obj):
        # L'objet doit avoir un champ 'utilisateur' ou être l'utilisateur lui-même
        if hasattr(obj, 'utilisateur'):
            return obj.utilisateur == request.user
        return obj == request.user


class EstVendeur(BasePermission):
    """
    Vérifie que l'utilisateur est un vendeur ou un admin.
    Utilisé pour autoriser la création/modification de produits.
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            (request.user.is_vendeur or request.user.is_admin)
        )