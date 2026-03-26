"""
AbiCare - Audit Log Models
============================
Records every access, creation, update, deletion in the system.
Who accessed what, from which IP, at what time.
Cannot be deleted by normal users — admin-only read.
"""

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class AuditLog(models.Model):
    """
    Immutable log entry for every significant system action.
    Written automatically by the AuditMiddleware and log_action() utility.
    """

    # ── Action types ──────────────────────────────────────────────────────────
    ACTION_CHOICES = [
        ('LOGIN', '🔐 Login'),
        ('LOGOUT', '🚪 Logout'),
        ('LOGIN_FAIL', '⚠️ Failed Login'),
        ('VIEW', '👁 View'),
        ('CREATE', '✅ Create'),
        ('UPDATE', '✏️ Update'),
        ('DELETE', '🗑 Delete'),
        ('DOWNLOAD', '⬇️ Download'),
        ('UPLOAD', '⬆️ Upload'),
        ('APPROVE', '✔️ Approve'),
        ('REVOKE', '✖️ Revoke'),
        ('TELECONSULT', '📹 Teleconsult'),
    ]

    # ── Fields ────────────────────────────────────────────────────────────────
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs',
        help_text="User who performed the action. NULL if unauthenticated."
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    description = models.TextField(help_text="Human-readable description of the action.")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    url_path = models.CharField(max_length=500, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        ordering = ['-timestamp']
        # Ensure logs are never accidentally modified
        default_permissions = ('view',)   # no add/change/delete from admin UI

    def __str__(self):
        user_str = self.user.username if self.user else "Anonymous"
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}] {user_str} — {self.get_action_display()}"
