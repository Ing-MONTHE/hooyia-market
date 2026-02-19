"""
HooYia Market — notifications/context_processors.py
Context processor pour injecter le badge de notifications dans tous les templates.

Fonctionne comme cart/context_processors.py (badge panier).
Injecte 'notif_count' dans chaque template HTML rendu par Django.

Usage dans les templates :
  <span class="badge">{{ notif_count }}</span>

Enregistré dans config/settings.py → TEMPLATES → OPTIONS → context_processors.
"""


def notif_count(request):
    """
    Injecte le nombre de notifications non lues de l'utilisateur connecté.
    Retourne 0 pour les utilisateurs anonymes.

    Appelé automatiquement par Django à chaque rendu de template.
    """
    if request.user.is_authenticated:
        from apps.notifications.models import Notification
        count = Notification.objects.filter(
            utilisateur=request.user,
            is_read=False
        ).count()
        return {'notif_count': count}
    return {'notif_count': 0}