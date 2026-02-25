"""
Les vues HTML de l'application users.
Ces vues retournent des pages HTML au navigateur
(contrairement aux api_views qui retournent du JSON).

Pages gérées :
  - Inscription
  - Connexion / Déconnexion
  - Vérification email
  - Profil utilisateur
  - Gestion des adresses
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from .models import AdresseLivraison, TokenVerificationEmail
from .forms import InscriptionForm, ConnexionForm


# ═══════════════════════════════════════════════════════════════
# VUE — Inscription
# ═══════════════════════════════════════════════════════════════

def inscription(request):
    """
    GET  → affiche le formulaire d'inscription
    POST → valide les données et crée le compte
    """
    # Si l'utilisateur est déjà connecté, on le redirige
    if request.user.is_authenticated:
        return redirect('products:accueil')

    if request.method == 'POST':
        form = InscriptionForm(request.POST)
        if form.is_valid():
            # Crée l'utilisateur (is_active=False par défaut)
            user = form.save()
            messages.success(
                request,
                f"Compte créé ! Vérifiez votre email {user.email} pour activer votre compte."
            )
            return redirect('users:connexion')
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = InscriptionForm()

    return render(request, 'users/register.html', {'form': form})


# ═══════════════════════════════════════════════════════════════
# VUE — Connexion
# ═══════════════════════════════════════════════════════════════

def connexion(request):
    """
    GET  → affiche le formulaire de connexion
    POST → vérifie les identifiants et connecte l'utilisateur
    """
    if request.user.is_authenticated:
        return redirect('products:accueil')

    if request.method == 'POST':
        form = ConnexionForm(request.POST)
        if form.is_valid():
            email    = form.cleaned_data['email']
            password = form.cleaned_data['password']

            # Vérifie les identifiants
            user = authenticate(request, username=email, password=password)

            if user is not None:
                # Vérifie que le compte est actif (email vérifié)
                if not user.is_active:
                    messages.warning(
                        request,
                        "Votre compte n'est pas encore activé. "
                        "Vérifiez votre email."
                    )
                    return redirect('users:connexion')

                # Connecte l'utilisateur et met à jour la dernière connexion
                login(request, user)
                user.derniere_connexion = timezone.now()
                user.save(update_fields=['derniere_connexion'])

                messages.success(request, f"Bienvenue {user.get_short_name()} !")

                # Redirige vers la page demandée avant la connexion
                # ou vers l'accueil par défaut
                next_url = request.GET.get('next', '/')
                return redirect(next_url)

            else:
                messages.error(request, "Email ou mot de passe incorrect.")
    else:
        form = ConnexionForm()

    return render(request, 'users/login.html', {'form': form})


# ═══════════════════════════════════════════════════════════════
# VUE — Déconnexion
# ═══════════════════════════════════════════════════════════════

@login_required
def deconnexion(request):
    """
    Déconnecte l'utilisateur et le redirige vers l'accueil.
    On utilise POST pour la déconnexion (sécurité CSRF).
    """
    logout(request)
    messages.info(request, "Vous êtes déconnecté.")
    return redirect('products:accueil')


# ═══════════════════════════════════════════════════════════════
# VUE — Vérification email
# L'utilisateur clique sur le lien reçu par email
# ═══════════════════════════════════════════════════════════════

def verifier_email(request, token):
    """
    Reçoit le token depuis l'URL.
    Vérifie qu'il est valide et non expiré.
    Active le compte si tout est bon.
    """
    try:
        token_obj = TokenVerificationEmail.objects.get(token=token)
    except TokenVerificationEmail.DoesNotExist:
        messages.error(request, "Lien de vérification invalide.")
        return redirect('users:connexion')

    # Vérifie que le token n'a pas expiré (24h)
    if token_obj.est_expire():
        messages.error(
            request,
            "Ce lien a expiré. Inscrivez-vous à nouveau."
        )
        # Supprime le token et l'utilisateur non activé
        token_obj.utilisateur.delete()
        return redirect('users:inscription')

    # Active le compte
    user = token_obj.utilisateur
    user.is_active      = True
    user.email_verifie  = True
    user.save(update_fields=['is_active', 'email_verifie'])

    # Supprime le token (usage unique)
    token_obj.delete()

    messages.success(
        request,
        "Votre compte est activé ! Vous pouvez vous connecter."
    )
    return redirect('users:connexion')


# ═══════════════════════════════════════════════════════════════
# VUE — Profil utilisateur
# ═══════════════════════════════════════════════════════════════

@login_required
def profil(request):
    """
    Affiche et permet de modifier le profil de l'utilisateur connecté.
    GET  → affiche le profil
    POST → met à jour les informations
    """
    if request.method == 'POST':
        action = request.POST.get('action', 'update_profil')
        if action == 'update_profil':
            user = request.user
            user.prenom    = request.POST.get('prenom', user.prenom).strip()
            user.nom       = request.POST.get('nom', user.nom).strip()
            user.telephone = request.POST.get('telephone', user.telephone).strip()
            username = request.POST.get('username', user.username).strip()
            from apps.users.models import CustomUser
            if username and username != user.username:
                if not CustomUser.objects.filter(username=username).exclude(pk=user.pk).exists():
                    user.username = username
            if request.FILES.get('photo_profil'):
                user.photo_profil = request.FILES['photo_profil']
            user.save()
            messages.success(request, "Profil mis à jour avec succès.")
            return redirect('users:profil')

    adresses = request.user.adresses.all()
    context = { 'adresses': adresses }
    return render(request, 'users/profile.html', context)


# ═══════════════════════════════════════════════════════════════
# VUE — Ajouter une adresse de livraison
# ═══════════════════════════════════════════════════════════════

@login_required
def ajouter_adresse(request):
    """
    Permet à l'utilisateur d'ajouter une nouvelle adresse de livraison.
    """
    from .forms import AdresseForm

    if request.method == 'POST':
        form = AdresseForm(request.POST)
        if form.is_valid():
            adresse = form.save(commit=False)
            # Associe l'adresse à l'utilisateur connecté
            adresse.utilisateur = request.user
            adresse.save()
            messages.success(request, "Adresse ajoutée avec succès.")
            return redirect('users:profil')
    else:
        form = AdresseForm()

    return render(request, 'users/adresse_form.html', {'form': form})


# ═══════════════════════════════════════════════════════════════
# VUE — Supprimer une adresse de livraison
# ═══════════════════════════════════════════════════════════════

@login_required
def supprimer_adresse(request, adresse_id):
    """
    Supprime une adresse après vérification que
    l'utilisateur en est bien le propriétaire.
    """
    adresse = get_object_or_404(
        AdresseLivraison,
        id=adresse_id,
        utilisateur=request.user  # Sécurité : on ne peut supprimer que ses propres adresses
    )

    if request.method == 'POST':
        adresse.delete()
        messages.success(request, "Adresse supprimée.")

    return redirect('users:profil')

# ═══════════════════════════════════════════════════════════════
# VUE — Google OAuth2
# ═══════════════════════════════════════════════════════════════

import urllib.parse
import secrets
import requests as http_requests
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()

GOOGLE_AUTH_URL     = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL    = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v3/userinfo'


def google_login(request):
    """Redirige vers Google pour l'authentification."""
    state = secrets.token_urlsafe(16)
    request.session['google_oauth_state'] = state

    params = {
        'client_id':     settings.GOOGLE_CLIENT_ID,
        'redirect_uri':  settings.GOOGLE_REDIRECT_URI,
        'response_type': 'code',
        'scope':         'openid email profile',
        'state':         state,
        'access_type':   'online',
        'prompt':        'select_account',
    }
    url = GOOGLE_AUTH_URL + '?' + urllib.parse.urlencode(params)
    return redirect(url)


def google_callback(request):
    """Reçoit le code de Google, récupère le profil et connecte l'utilisateur."""
    # Vérification CSRF state
    state = request.GET.get('state', '')
    if state != request.session.get('google_oauth_state', ''):
        messages.error(request, "Erreur de sécurité OAuth. Réessayez.")
        return redirect('users:connexion')

    code = request.GET.get('code')
    if not code:
        messages.error(request, "Connexion Google annulée ou refusée.")
        return redirect('users:connexion')

    # Échange du code contre un access_token
    try:
        token_resp = http_requests.post(GOOGLE_TOKEN_URL, data={
            'code':          code,
            'client_id':     settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'redirect_uri':  settings.GOOGLE_REDIRECT_URI,
            'grant_type':    'authorization_code',
        }, timeout=10)
        token_data = token_resp.json()
    except Exception:
        messages.error(request, "Impossible de contacter Google. Réessayez.")
        return redirect('users:connexion')

    access_token = token_data.get('access_token')
    if not access_token:
        messages.error(request, "Échec de l'authentification Google.")
        return redirect('users:connexion')

    # Récupération du profil Google
    try:
        userinfo_resp = http_requests.get(
            GOOGLE_USERINFO_URL,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10
        )
        userinfo = userinfo_resp.json()
    except Exception:
        messages.error(request, "Impossible de récupérer le profil Google.")
        return redirect('users:connexion')

    email      = userinfo.get('email', '').lower()
    first_name = userinfo.get('given_name', '')
    last_name  = userinfo.get('family_name', '')
    google_id  = userinfo.get('sub', '')

    if not email:
        messages.error(request, "Impossible de récupérer votre email Google.")
        return redirect('users:connexion')

    # Connexion ou création du compte
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # Génère un username unique depuis l'email
        base_username = email.split('@')[0].replace('.', '_')[:30]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1

        user = User.objects.create_user(
            email    = email,
            username = username,
            password = None,
        )
        user.prenom        = first_name
        user.nom           = last_name
        user.is_active     = True
        user.email_verifie = True
        user.save()

    # Activer le compte si pas encore actif (cas edge)
    if not user.is_active:
        user.is_active     = True
        user.email_verifie = True
        user.save()

    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    messages.success(request, f"Bienvenue {user.prenom or user.username} ! 👋")
    return redirect(settings.LOGIN_REDIRECT_URL)