"""
HooYia Market — users/api_views.py

Les vues API retournent du JSON au lieu de HTML.
Elles sont consommées par JavaScript (fetch API) côté frontend.

Endpoints gérés :
  - POST /api/auth/register/         → Inscription
  - POST /api/auth/token/            → Connexion (JWT)
  - POST /api/auth/token/refresh/    → Renouveler token
  - GET/PUT /api/auth/profil/        → Voir/modifier profil
  - POST /api/auth/changer-password/ → Changer mot de passe
  - GET/POST /api/auth/adresses/     → Lister/ajouter adresses
  - DELETE /api/auth/adresses/<id>/  → Supprimer adresse
"""
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import CustomUser, AdresseLivraison
from .serializers import (
    InscriptionSerializer,
    ProfilSerializer,
    ChangerMotDePasseSerializer,
    AdresseLivraisonSerializer,
    UtilisateurPublicSerializer
)


# ═══════════════════════════════════════════════════════════════
# VUE API — Inscription
# POST /api/auth/register/
# ═══════════════════════════════════════════════════════════════

class InscriptionAPIView(generics.CreateAPIView):
    """
    Crée un nouveau compte utilisateur.
    Accessible sans être connecté (AllowAny).
    Après création, un email de vérification est envoyé
    automatiquement via le signal users/signals.py.
    """
    serializer_class   = InscriptionSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response({
            'message': f"Compte créé ! Vérifiez votre email {user.email} pour activer votre compte.",
            'email'  : user.email
        }, status=status.HTTP_201_CREATED)


# ═══════════════════════════════════════════════════════════════
# VUE API — Déconnexion (blacklist du refresh token)
# POST /api/auth/logout/
# ═══════════════════════════════════════════════════════════════

class DeconnexionAPIView(APIView):
    """
    Invalide le refresh token pour déconnecter l'utilisateur.
    SimpleJWT garde les tokens valides jusqu'à expiration,
    la blacklist permet de les invalider avant.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            # Récupère le refresh token envoyé dans le body
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)

            # Ajoute le token à la blacklist → il ne sera plus accepté
            token.blacklist()

            return Response(
                {'message': 'Déconnexion réussie.'},
                status=status.HTTP_200_OK
            )
        except Exception:
            return Response(
                {'erreur': 'Token invalide.'},
                status=status.HTTP_400_BAD_REQUEST
            )


# ═══════════════════════════════════════════════════════════════
# VUE API — Profil utilisateur connecté
# GET  /api/auth/profil/ → retourne le profil en JSON
# PUT  /api/auth/profil/ → met à jour le profil
# ═══════════════════════════════════════════════════════════════

class ProfilAPIView(generics.RetrieveUpdateAPIView):
    """
    Affiche et modifie le profil de l'utilisateur connecté.
    Chaque utilisateur ne voit et modifie QUE son propre profil.
    """
    serializer_class   = ProfilSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # Retourne toujours l'utilisateur connecté
        return self.request.user


# ═══════════════════════════════════════════════════════════════
# VUE API — Changer le mot de passe
# POST /api/auth/changer-password/
# ═══════════════════════════════════════════════════════════════

class ChangerMotDePasseAPIView(APIView):
    """
    Permet à l'utilisateur connecté de changer son mot de passe.
    Requiert l'ancien mot de passe pour confirmer l'identité.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangerMotDePasseSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {'message': 'Mot de passe changé avec succès.'},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ═══════════════════════════════════════════════════════════════
# VUE API — Adresses de livraison
# GET  /api/auth/adresses/     → liste les adresses
# POST /api/auth/adresses/     → ajoute une adresse
# ═══════════════════════════════════════════════════════════════

class AdresseListeAPIView(generics.ListCreateAPIView):
    """
    Liste et crée des adresses de livraison.
    Chaque utilisateur ne voit QUE ses propres adresses.
    """
    serializer_class   = AdresseLivraisonSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Filtre pour ne retourner que les adresses de l'utilisateur connecté
        return AdresseLivraison.objects.filter(utilisateur=self.request.user)


# ═══════════════════════════════════════════════════════════════
# VUE API — Détail / Suppression d'une adresse
# GET    /api/auth/adresses/<id>/ → détail adresse
# PUT    /api/auth/adresses/<id>/ → modifier adresse
# DELETE /api/auth/adresses/<id>/ → supprimer adresse
# ═══════════════════════════════════════════════════════════════

class AdresseDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    Détail, modification et suppression d'une adresse.
    Vérification que l'adresse appartient bien à l'utilisateur connecté.
    """
    serializer_class   = AdresseLivraisonSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Sécurité : on ne peut accéder qu'à ses propres adresses
        return AdresseLivraison.objects.filter(utilisateur=self.request.user)