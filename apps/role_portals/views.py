"""
AbiCare - Role Portals Views
================================
Each role has their own portal dashboard.
Separate login pages redirect automatically.
Admin can access any portal.
"""
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.views.decorators.cache import never_cache


ROLE_PORTALS = {
    'patient':      '/portal/',
    'doctor':       '/doctor-portal/',
    'nurse':        '/nurse-portal/',
    'lab_tech':     '/lab-portal/',
    'receptionist': '/reception-portal/',
    'admin':        '/dashboard/',
}


def _portal_login(request, role, template, redirect_url):
    """Generic login handler for all role portals."""
    if request.user.is_authenticated:
        if request.user.role == role or request.user.is_admin_staff:
            return redirect(redirect_url)
        messages.error(request,
            f"This portal is for {role.replace('_',' ').title()}s only. "
            f"You are logged in as {request.user.get_role_display()}.")
        return redirect(ROLE_PORTALS.get(request.user.role, '/dashboard/'))

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user     = authenticate(request, username=username, password=password)

        if user and user.is_active:
            # Allow admin to log in anywhere
            if user.role == role or user.is_admin_staff:
                login(request, user)
                if user.must_change_password:
                    return redirect('accounts:force_change_password')
                return redirect(redirect_url)
            else:
                messages.error(request,
                    f"This portal is for {role.replace('_',' ').title()}s. "
                    f"Your role is {user.get_role_display()}. "
                    f"Please use the correct portal.")
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, template, {
        'page_title': f"{role.replace('_',' ').title()} Portal Login",
        'role':       role,
    })


@never_cache
def doctor_login_view(request):
    return _portal_login(request, 'doctor',
                         'role_portals/doctor_login.html', '/doctor-portal/')


@never_cache
def nurse_login_view(request):
    return _portal_login(request, 'nurse',
                         'role_portals/nurse_login.html', '/nurse-portal/')


@never_cache
def lab_login_view(request):
    return _portal_login(request, 'lab_tech',
                         'role_portals/lab_login.html', '/lab-portal/')


@never_cache
def reception_login_view(request):
    return _portal_login(request, 'receptionist',
                         'role_portals/reception_login.html', '/reception-portal/')


from django.contrib.auth.decorators import login_required


@login_required
def doctor_portal_view(request):
    if not (request.user.role == 'doctor' or request.user.is_admin_staff):
        messages.error(request, "Doctor portal — access denied.")
        return redirect(ROLE_PORTALS.get(request.user.role, '/dashboard/'))

    from apps.patients.models import Patient
    from apps.billing.models import Bill
    from apps.appointments.models import Appointment
    from django.utils import timezone

    today    = timezone.now().date()
    patients = Patient.objects.filter(
        assigned_doctor=request.user, is_active=True
    ) if request.user.role == 'doctor' else Patient.objects.filter(is_active=True)

    pending_bills = Bill.objects.filter(
        created_by=request.user, status='draft'
    ) if request.user.role == 'doctor' else Bill.objects.filter(status='draft')

    todays_appts = Appointment.objects.filter(
        appointment_date=today,
        status__in=['scheduled', 'confirmed']
    )
    if request.user.role == 'doctor':
        todays_appts = todays_appts.filter(doctor=request.user)

    return render(request, 'role_portals/doctor_portal.html', {
        'page_title':   'Doctor Portal',
        'patients':     patients[:10],
        'patient_count': patients.count(),
        'pending_bills': pending_bills[:5],
        'todays_appts':  todays_appts[:10],
        'today':         today,
    })


@login_required
def nurse_portal_view(request):
    if not (request.user.role == 'nurse' or request.user.is_admin_staff):
        messages.error(request, "Nurse portal — access denied.")
        return redirect(ROLE_PORTALS.get(request.user.role, '/dashboard/'))

    from apps.billing.models import Bill
    from apps.queue.models import QueueEntry
    from django.utils import timezone

    today = timezone.now().date()

    bills_to_action = Bill.objects.filter(
        assigned_nurse=request.user,
        status__in=['sent_to_nurse', 'sent_to_patient', 'partially_paid']
    ).select_related('patient', 'created_by')

    todays_queue = QueueEntry.objects.filter(
        queue_date=today,
        status__in=['waiting', 'called']
    ).select_related('patient')

    return render(request, 'role_portals/nurse_portal.html', {
        'page_title':       'Nurse Portal',
        'bills_to_action':  bills_to_action,
        'todays_queue':     todays_queue,
        'today':            today,
    })


@login_required
def lab_portal_view(request):
    if not (request.user.role == 'lab_tech' or request.user.is_admin_staff):
        messages.error(request, "Lab portal — access denied.")
        return redirect(ROLE_PORTALS.get(request.user.role, '/dashboard/'))

    from apps.lab_results.models import LabResult
    pending = LabResult.objects.filter(
        status__in=['pending', 'processing']
    ).select_related('patient', 'template')

    return render(request, 'role_portals/lab_portal.html', {
        'page_title': 'Laboratory Portal',
        'pending':    pending[:20],
    })


@login_required
def reception_portal_view(request):
    if not (request.user.role == 'receptionist' or request.user.is_admin_staff):
        messages.error(request, "Reception portal — access denied.")
        return redirect(ROLE_PORTALS.get(request.user.role, '/dashboard/'))

    from apps.patients.models import Patient
    from apps.appointments.models import Appointment
    from apps.queue.models import QueueEntry
    from django.utils import timezone

    today     = timezone.now().date()
    today_q   = QueueEntry.objects.filter(queue_date=today).count()
    today_appt = Appointment.objects.filter(
        appointment_date=today,
        status__in=['scheduled', 'confirmed']
    ).count()
    recent_patients = Patient.objects.filter(
        is_active=True
    ).order_by('-created_at')[:8]

    return render(request, 'role_portals/reception_portal.html', {
        'page_title':       'Reception Portal',
        'today_queue':      today_q,
        'today_appts':      today_appt,
        'recent_patients':  recent_patients,
        'today':            today,
    })

# Create your views here.
