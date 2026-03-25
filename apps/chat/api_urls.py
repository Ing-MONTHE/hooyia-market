"""
Routes API pour le chat.

Endpoints (préfixe 'api/chat/' défini dans config/urls.py) :
  GET  /api/chat/                      → liste des conversations
  POST /api/chat/creer/                → démarrer une conversation
  GET  /api/chat/<id>/                 → détail + messages d'une conversation
  POST /api/chat/<id>/envoyer/         → envoyer un message texte (fallback HTTP)
  POST /api/chat/<id>/upload/          → uploader un fichier ← NOUVEAU
  GET  /api/chat/<id>/fichiers/        → lister les fichiers partagés ← NOUVEAU
  POST /api/chat/<id>/marquer_lu/      → marquer les messages comme lus
"""
from django.urls import path
from . import api_views

urlpatterns = [

    # ── Conversations ────────────────────────────────────────────
    path('',
         api_views.ConversationListeAPIView.as_view(),
         name='chat-liste'),

    path('creer/',
         api_views.ConversationCreerAPIView.as_view(),
         name='chat-creer'),

    # ── Détail conversation ──────────────────────────────────────
    path('<int:pk>/',
         api_views.ConversationDetailAPIView.as_view(),
         name='chat-detail'),

    # ── Actions sur une conversation ─────────────────────────────
    path('<int:pk>/envoyer/',
         api_views.EnvoyerMessageAPIView.as_view(),
         name='chat-envoyer'),

    path('<int:pk>/upload/',          # ← NOUVEAU
         api_views.UploadFichierAPIView.as_view(),
         name='chat-upload'),

    path('<int:pk>/fichiers/',        # ← NOUVEAU
         api_views.FichiersConversationAPIView.as_view(),
         name='chat-fichiers'),

    path('<int:pk>/marquer_lu/',
         api_views.MarquerLuAPIView.as_view(),
         name='chat-marquer-lu'),
]