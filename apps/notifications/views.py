"""
HooYia Market — apps/notifications/views.py
Vue HTML pour la page notifications du client.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def mes_notifications(request):
    """
    Page notifications de l'utilisateur connecté.
    Les données sont chargées en AJAX via /api/notifications/.
    """
    return render(request, "notifications/mes_notifications.html")
