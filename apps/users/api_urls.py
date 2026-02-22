"""
HooYia Market — users/api_urls.py
Routes pour l'API REST de l'app users.
Toutes retournent du JSON.
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from . import api_views

class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer

urlpatterns = [
    # ── Authentification JWT ──────────────────────────────────
    # POST → envoie email+password → reçoit access+refresh tokens
    path('token/',          TokenObtainPairView.as_view(), name='token_obtain'),
    # POST → envoie refresh token → reçoit nouveau access token
    path('token/refresh/',  TokenRefreshView.as_view(),    name='token_refresh'),

    # ── Compte ───────────────────────────────────────────────
    path('register/',          api_views.InscriptionAPIView.as_view(),     name='api_inscription'),
    path('logout/',            api_views.DeconnexionAPIView.as_view(),     name='api_deconnexion'),
    path('profil/',            api_views.ProfilAPIView.as_view(),          name='api_profil'),
    path('changer-password/',  api_views.ChangerMotDePasseAPIView.as_view(), name='api_changer_mdp'),

    # ── Adresses ─────────────────────────────────────────────
    path('adresses/',          api_views.AdresseListeAPIView.as_view(),    name='api_adresses'),
    path('adresses/<int:pk>/', api_views.AdresseDetailAPIView.as_view(),   name='api_adresse_detail'),

    # ── Admin ────────────────────────────────────────────────
    path('utilisateurs/',             api_views.ListeUtilisateursAdminAPIView.as_view(), name='api_liste_users'),
    path('utilisateurs/<int:pk>/toggle_actif/', api_views.ToggleUtilisateurAPIView.as_view(), name='api_toggle_user'),
]