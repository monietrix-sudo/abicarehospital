"""AbiCare - Audit Log Views."""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator
from .models import AuditLog


@login_required
def audit_log_list(request):
    """Admin/superuser view of all audit logs."""
    if not (request.user.is_admin_staff or request.user.is_superuser):
        from django.shortcuts import redirect
        return redirect('patients:dashboard')

    logs = AuditLog.objects.select_related('user').all()
    q = request.GET.get('q', '')
    action = request.GET.get('action', '')
    if q:
        logs = logs.filter(Q(user__username__icontains=q) | Q(description__icontains=q) | Q(ip_address__icontains=q))
    if action:
        logs = logs.filter(action=action)

    paginator = Paginator(logs, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'audit_logs/audit_list.html', {
        'page_title': 'Audit Logs',
        'page_obj': page_obj,
        'q': q,
        'action_filter': action,
        'action_choices': AuditLog.ACTION_CHOICES,
    })
