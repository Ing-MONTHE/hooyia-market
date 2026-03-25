"""
Vues HTML pour le chat.

Ces vues rendent les templates HTML qui utilisent ensuite
le WebSocket (chat.js) et l'API JSON (api_views.py) pour
afficher et envoyer les messages en temps réel.
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext_lazy as _

from .models import Conversation


@login_required
def chat_liste(request):
    """
    GET /chat/
    Affiche la liste des conversations de l'utilisateur connecté.
    Le template récupère les données via fetch('/api/chat/') en JS.
    """
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from datetime import timedelta
    User = get_user_model()
    admin = User.objects.filter(is_admin=True, is_active=True).first()
    admin_online = False
    if admin and admin.last_login:
        admin_online = (timezone.now() - admin.last_login) < timedelta(minutes=15)
    return render(request, 'chat/chat_liste.html', {
        'admin_id': admin.id if admin else None,
        'admin_username': admin.username if admin else None,
        'admin_online': admin_online,
    })


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
        return HttpResponseForbidden(_("Vous n'êtes pas membre de cette conversation."))

    return render(request, 'chat/chat_detail.html', {
        'conversation_id': pk,
        'interlocuteur'  : conversation.get_autre_participant(request.user),
    })