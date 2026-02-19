"""
HooYia Market — chat/urls.py
Routes HTML pour le chat.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('',          views.chat_liste,  name='chat-liste'),
    path('<int:pk>/', views.chat_detail, name='chat-detail'),
]