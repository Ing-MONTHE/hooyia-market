"""
HooYia Market — chat/views.py
Vues HTML pour le chat.

Ces vues rendent les templates HTML qui utilisent ensuite
le WebSocket (chat.js) et l'API JSON (api_views.py) pour
afficher et envoyer les messages en temps réel.
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q

from .models import Conversation


@login_required
def chat_liste(request):
    """
    GET /chat/
    Affiche la liste des conversations de l'utilisateur connecté.
    Le template récupère les données via fetch('/api/chat/') en JS.
    """
    return render(request, 'chat/chat_liste.html')


@login_required
def chat_detail(request, pk):
    """
    GET /chat/<id>/
    Affiche l'interface de chat d'une conversation.
    Vérifie que l'utilisateur est bien participant avant d'afficher.
    Le template se connecte ensuite au WebSocket ws/chat/<id>/.
    """
    # Sécurité : l'utilisateur doit être participant de la conversation
    conversation = get_object_or_404(
        Conversation,
        id=pk,
    )
    if conversation.participant1 != request.user and conversation.participant2 != request.user:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Vous n'êtes pas membre de cette conversation.")

    return render(request, 'chat/chat_detail.html', {
        'conversation_id': pk,
        'interlocuteur'  : conversation.get_autre_participant(request.user),
    })