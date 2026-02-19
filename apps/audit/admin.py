from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    # Colonnes affichées dans la liste admin
    list_display  = ['action', 'url', 'utilisateur', 'status_code', 'date']
    list_filter   = ['action', 'status_code']
    search_fields = ['url', 'utilisateur__username']
    readonly_fields = ['action', 'url', 'utilisateur', 'status_code', 'date', 'note']

    # Personne ne peut créer ou supprimer un log depuis l'admin
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False