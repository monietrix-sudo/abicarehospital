"""
AbiCare - Audit Log Utility
============================
Call log_action() from any view to record an action.
Usage:
    from apps.audit_logs.utils import log_action
    log_action(request.user, 'VIEW', request, "Viewed patient ABI-2024-00001")
"""

from .models import AuditLog


def get_client_ip(request):
    """Extract real IP from request headers (handles proxies/load balancers)."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # X-Forwarded-For can be a comma-separated list; take the first (real client IP)
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def log_action(user, action, request, description):
    """
    Create an AuditLog entry.

    Args:
        user:        The User object (or None if unauthenticated).
        action:      Action code string — must match AuditLog.ACTION_CHOICES.
        request:     The Django HttpRequest (for IP and user-agent).
        description: Human-readable text describing what happened.
    """
    try:
        AuditLog.objects.create(
            user=user,
            action=action,
            description=description,
            ip_address=get_client_ip(request) if request else None,
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:300] if request else '',
            url_path=request.path if request else '',
        )
    except Exception:
        # Never let audit logging crash the main request flow
        pass
