"""
HooYia Market — cart/context_processors.py
Injecte automatiquement le nombre d'articles du panier dans tous les templates.

Un context processor est une fonction appelée à chaque requête HTTP.
Elle retourne un dictionnaire injecté dans le contexte de tous les templates,
sans avoir besoin de le passer manuellement dans chaque vue.

Activation dans settings.py → TEMPLATES → context_processors :
  'apps.cart.context_processors.cart_count'

Usage dans les templates :
  {{ cart_count }}  → affiche le badge avec le nombre d'articles
"""


# ═══════════════════════════════════════════════════════════════
# CONTEXT PROCESSOR — Nombre d'articles dans le panier
# ═══════════════════════════════════════════════════════════════

def cart_count(request):
    """
    Retourne le nombre total d'articles dans le panier de l'utilisateur connecté.
    Disponible dans tous les templates via {{ cart_count }}.
    Retourne 0 pour les visiteurs non connectés.

    Optimisation :
      On ne charge que le nombre (aggregate SQL), pas tout le panier,
      pour garder chaque requête HTTP légère.
    """
    # Les visiteurs non connectés n'ont pas de panier
    if not request.user.is_authenticated:
        return {'cart_count': 0}

    try:
        # Accède au panier via la relation OneToOne (user.panier)
        # Appelle la propriété nombre_articles (aggregate SQL)
        count = request.user.panier.nombre_articles
    except Exception:
        # Si le panier n'existe pas encore (cas rare), on retourne 0
        count = 0

    return {'cart_count': count}