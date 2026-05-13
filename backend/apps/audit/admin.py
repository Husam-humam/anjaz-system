from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'created_at', 'action_type', 'actor', 'actor_role',
        'target_model', 'target_id', 'qism',
    )
    list_filter = ('action_type', 'actor_role', 'target_model', 'created_at')
    search_fields = ('target_repr', 'reason', 'actor__full_name', 'actor__username')
    readonly_fields = (
        'action_type', 'actor', 'actor_role', 'target_model', 'target_id',
        'target_repr', 'qism', 'field_changes', 'reason', 'metadata', 'created_at',
    )
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
