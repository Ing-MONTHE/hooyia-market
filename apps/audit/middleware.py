"""
HooYia Market — audit/middleware.py
Enregistre automatiquement toutes les actions importantes (POST, PUT, DELETE)
Ce middleware s'exécute à chaque requête HTTP, comme une caméra de surveillance
"""
import json
import logging

logger = logging.getLogger(__name__)


class AuditLogMiddleware:
    """
    Intercepte chaque requête HTTP.
    Si c'est une action qui modifie des données (POST/PUT/PATCH/DELETE),
    on l'enregistre dans les logs pour garder une trace.
    """

    def __init__(self, get_response):
        # get_response = la fonction qui traite la requête après ce middleware
        self.get_response = get_response

    def __call__(self, request):

        # ── Avant la vue ──────────────────────────────────────
        response = self.get_response(request)

        # ── Après la vue : on enregistre si action importante ──
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            user = request.user if request.user.is_authenticated else 'Anonyme'
            logger.info(
                f"[AUDIT] {request.method} | "
                f"URL: {request.path} | "
                f"User: {user} | "
                f"Status: {response.status_code}"
            )

        return response