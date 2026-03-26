"""AbiCare - Audit Log Admin."""

from django.contrib import admin
from django.utils.html import format_html
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only audit log viewer in admin panel."""
    list_display = ['timestamp', 'user_display', 'action_badge', 'description_short', 'ip_address', 'url_path']
    list_filter = ['action', 'timestamp', 'user']
    search_fields = ['user__username', 'description', 'ip_address', 'url_path']
    readonly_fields = [f.name for f in AuditLog._meta.get_fields() if hasattr(f, 'name')]
    ordering = ['-timestamp']
    list_per_page = 50
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return request.user.is_superuser

    def user_display(self, obj):
        return obj.user.username if obj.user else format_html('<span style="color:#999;">Anonymous</span>')
    user_display.short_description = 'User'

    def action_badge(self, obj):
        colors = {
            'LOGIN': '#00C49A', 'LOGOUT': '#6C757D', 'LOGIN_FAIL': '#DC3545',
            'VIEW': '#17A2B8', 'CREATE': '#28A745', 'UPDATE': '#FFC107',
            'DELETE': '#DC3545', 'UPLOAD': '#0A5C8A', 'DOWNLOAD': '#6610F2',
            'APPROVE': '#28A745', 'REVOKE': '#DC3545', 'TELECONSULT': '#E83E8C',
        }
        color = colors.get(obj.action, '#6C757D')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:10px;font-size:11px;">{}</span>',
            color, obj.get_action_display()
        )
    action_badge.short_description = 'Action'

    def description_short(self, obj):
        return obj.description[:80] + '…' if len(obj.description) > 80 else obj.description
    description_short.short_description = 'Description'
