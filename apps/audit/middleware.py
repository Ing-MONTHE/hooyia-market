"""
Middleware d'audit résiduel.
Enregistre les actions HTTP qui ne sont PAS couvertes par les signals Django
(ex: appels API génériques sans modèle associé).

Les actions métier principales (commandes, messages, produits, etc.)
sont gérées par apps/audit/audit_signals.py via les signals Django.
"""
import threading

METHOD_TO_ACTION = {
    'POST':   'CREATE',
    'PUT':    'UPDATE',
    'PATCH':  'UPDATE',
    'DELETE': 'DELETE',
}

# URLs ignorées (bruit, boucle infinie, fichiers statiques)
IGNORED_PATHS = (
    '/static/', '/media/', '/favicon.ico',
    '/api/audit/',
    '/admin/jsi18n/',
)

# URLs couvertes par les signals → pas besoin de double log
SIGNAL_COVERED = (
    '/api/commandes',
    '/api/produits',
    '/api/categories',
    '/api/avis',
    '/api/chat',
    '/api/panier',
    '/api/cart',
    '/api/users',
    '/api/comptes',
    '/api/notifications',
    '/login',
    '/logout',
)

SPECIAL_ROUTES = {
    'login':  'LOGIN',
    'logout': 'LOGOUT',
}

ACTION_LABELS = {
    'CREATE': 'Création',
    'UPDATE': 'Modification',
    'DELETE': 'Suppression',
    'LOGIN':  'Connexion',
    'LOGOUT': 'Déconnexion',
}


def _save_log(user, action, path, status_code, note=''):
    try:
        from .models import AuditLog
        AuditLog.objects.create(
            utilisateur=user if (user and getattr(user, 'is_authenticated', False)) else None,
            action=action,
            url=path,
            status_code=status_code,
            note=note,
        )
    except Exception:
        pass


class AuditLogMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        path = request.path
        method = request.method

        # Ignorer GET et chemins non pertinents
        if method == 'GET':
            return response
        if any(path.startswith(p) for p in IGNORED_PATHS):
            return response

        # Ignorer ce qui est déjà couvert par les signals
        if any(path.startswith(p) for p in SIGNAL_COVERED):
            return response

        status = response.status_code
        user = getattr(request, 'user', None)

        path_lower = path.strip('/').split('/')[-1]
        if path_lower in SPECIAL_ROUTES and status in (200, 302):
            action = SPECIAL_ROUTES[path_lower]
        else:
            action = METHOD_TO_ACTION.get(method, method)

        label = ACTION_LABELS.get(action, action)
        note = f"{label} — {path}"

        _save_log(user, action, path, status, note)

        return response