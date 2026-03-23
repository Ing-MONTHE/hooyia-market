"""
HooYia Market — urls.py
Point d'entrée de toutes les URLs du projet
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.views.i18n import JavaScriptCatalog
from apps.products.api_views import CategorieViewSet, StatsOverviewView

urlpatterns = [
    # Changement de langue (POST) — hors i18n_patterns pour rester accessible
    path('i18n/', include('django.conf.urls.i18n')),

    # ── API REST (pas de préfixe langue) ────────────────────
    path('api/auth/',  include('apps.users.api_urls')),
    path('api/produits/',      include('apps.products.api_urls')),
    path('api/categories/',    CategorieViewSet.as_view({'get': 'list', 'post': 'create'})),
    path('api/categories/<int:pk>/', CategorieViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'put': 'update', 'delete': 'destroy'})),
    path('api/panier/',        include('apps.cart.api_urls')),
    path('api/commandes/',     include('apps.orders.api_urls')),
    path('api/avis/',          include('apps.reviews.api_urls')),
    path('api/avis-app/',      include('apps.reviews.api_urls_app')),
    path('api/notifications/', include('apps.notifications.api_urls')),
    path('api/chat/',          include('apps.chat.api_urls')),

    # ── Stats Dashboard ──────────────────────────────────────
    path('api/stats/overview/', StatsOverviewView.as_view(), name='stats-overview'),
    path('api/audit/',          include('apps.audit.api_urls')),
]

# ── Pages HTML avec préfixe langue (/fr/... ou /en/...) ──────
urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    path('jsi18n/', JavaScriptCatalog.as_view(), name='javascript-catalog'),  # Catalogue JS i18n
    path('',          include('apps.products.urls')),
    path('compte/',    include('apps.users.urls')),
    path('panier/',   include('apps.cart.urls')),
    path('commandes/', include('apps.orders.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('chat/',     include('apps.chat.urls')),
    prefix_default_language=False,  # /fr/ optionnel pour la langue par défaut
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])