from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # Checkout — passer_commande est un alias de checkout
    path('',                views.checkout,     name='checkout'),
    path('passer/',         views.checkout,     name='passer_commande'),
    # Confirmation
    path('<int:pk>/',       views.confirmation, name='confirmation'),
    # Historique
    path('historique/',     views.historique,   name='historique'),
]