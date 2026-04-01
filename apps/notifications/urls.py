"""
HooYia Market — apps/notifications/urls.py
URLs HTML pour les notifications client.
"""

from django.urls import path
from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.mes_notifications, name="liste"),
]
