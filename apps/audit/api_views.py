"""
API REST pour le journal d'audit.
GET /api/audit/ → liste paginée des logs (admin uniquement)
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.pagination import PageNumberPagination

from .models import AuditLog


class AuditPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'count':     self.page.paginator.count,
            'next':      self.get_next_link(),
            'previous':  self.get_previous_link(),
            'page_size': self.page_size,
            'results':   data,
        })


class AuditLogListView(APIView):
    """
    GET /api/audit/
    Retourne la liste paginée des logs d'audit.
    Accessible aux admins et staff uniquement.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        qs = AuditLog.objects.select_related('utilisateur').order_by('-date')

        paginator = AuditPagination()
        page = paginator.paginate_queryset(qs, request)

        data = [
            {
                'id':             log.id,
                'action':         log.action,
                'url':            log.url,
                'status_code':    log.status_code,
                'utilisateur_nom': log.utilisateur.username if log.utilisateur else '—',
                'note':           log.note,
                'date':           log.date.isoformat(),
                # Alias pour compatibilité avec le JS (entry.date_action)
                'date_action':    log.date.isoformat(),
                'description':    f"{log.action} — {log.url}",
            }
            for log in page
        ]

        return paginator.get_paginated_response(data)