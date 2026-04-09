from django.core.cache import cache
from .models import Categorie


def categories_navbar(request):
    categories = cache.get("categories_racines")
    if not categories:
        categories = Categorie.objects.filter(
            parent=None, est_active=True
        ).prefetch_related("sous_categories")
        cache.set("categories_racines", categories, 3600)
    return {"categories": categories}
