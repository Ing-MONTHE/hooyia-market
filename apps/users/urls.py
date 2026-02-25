from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # Inscription
    path('inscription/',            views.inscription,      name='inscription'),
    # Connexion
    path('connexion/',              views.connexion,         name='connexion'),
    # Déconnexion
    path('deconnexion/',            views.deconnexion,       name='deconnexion'),
    # Vérification email (token dans l'URL)
    path('verifier-email/<uuid:token>/', views.verifier_email, name='verifier_email'),
    # Profil
    path('profil/',                 views.profil,            name='profil'),
    # Adresses
    path('adresses/ajouter/',       views.ajouter_adresse,   name='ajouter_adresse'),
    path('adresses/<int:adresse_id>/supprimer/', views.supprimer_adresse, name='supprimer_adresse'),
    path('google/login/',    views.google_login,    name='google_login'),
    path('google/callback/',  views.google_callback, name='google_callback'),
]