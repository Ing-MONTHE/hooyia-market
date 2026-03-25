"""
Routes HTML pour le chat.
"""
from django.urls import path
from . import views

app_name = 'chat' 

urlpatterns = [
    path('',          views.chat_liste,  name='chat-liste'),
    path('<int:pk>/', views.chat_detail, name='chat-detail'),
]