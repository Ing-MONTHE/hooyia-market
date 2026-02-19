"""
HooYia Market — urls.py
Point d'entrée de toutes les URLs du projet
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('__debug__/', include('debug_toolbar.urls')),

    # ── Pages HTML ──────────────────────────────────────────
    path('',          include('apps.products.urls')),
    path('compte/',    include('apps.users.urls')),
    path('panier/',   include('apps.cart.urls')),
    path('commandes/', include('apps.orders.urls')),
    path('chat/',     include('apps.chat.urls')),

    # ── API REST ─────────────────────────────────────────────
    path('api/auth/',  include('apps.users.api_urls')),
    path('api/produits/',      include('apps.products.api_urls')),
    path('api/panier/',        include('apps.cart.api_urls')),
    path('api/commandes/',     include('apps.orders.api_urls')),
    path('api/avis/',          include('apps.reviews.api_urls')),
    path('api/notifications/', include('apps.notifications.api_urls')),
    path('api/chat/',          include('apps.chat.api_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])