"""AbiCare - Teleconsult Views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import ConsultLink
from apps.audit_logs.utils import log_action

@login_required
def consult_links_view(request):
    """Manage a doctor's saved teleconsult links."""
    if not (request.user.is_doctor or request.user.is_admin_staff):
        messages.error(request, "Access denied.")
        return redirect('patients:dashboard')

    if request.method == 'POST':
        ConsultLink.objects.create(
            doctor=request.user if request.user.is_doctor else
                   __import__('apps.accounts.models', fromlist=['User']).User.objects.get(id=request.POST['doctor_id']),
            platform=request.POST['platform'],
            link=request.POST['link'],
            label=request.POST.get('label', 'Default Room'),
        )
        messages.success(request, "Consult link saved.")
        return redirect('teleconsult:links')

    links = ConsultLink.objects.filter(is_active=True)
    if request.user.is_doctor:
        links = links.filter(doctor=request.user)

    return render(request, 'teleconsult/consult_links.html', {
        'page_title': 'Teleconsult Links',
        'links': links,
        'platform_choices': ConsultLink.PLATFORM_CHOICES,
    })
