"""
AbiCare - Appointments Views
==============================
Schedule appointments, manage teleconsult links, approve access.
Teleconsult join is gated: doctor must explicitly approve first.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import JsonResponse

from .models import Appointment
from apps.patients.models import Patient
from apps.accounts.models import User
from apps.audit_logs.utils import log_action


@login_required
def appointment_list_view(request):
    """List all appointments with filters by date, status, doctor."""
    date_filter = request.GET.get('date', '')
    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('type', '')

    appointments = Appointment.objects.select_related('patient', 'doctor').all()

    # Doctors only see their own appointments
    if request.user.is_doctor:
        appointments = appointments.filter(doctor=request.user)

    # Patients only see their own
    if request.user.is_patient_user and hasattr(request.user, 'patient_profile'):
        appointments = appointments.filter(patient=request.user.patient_profile)

    if date_filter:
        appointments = appointments.filter(appointment_date=date_filter)
    if status_filter:
        appointments = appointments.filter(status=status_filter)
    if type_filter:
        appointments = appointments.filter(appointment_type=type_filter)

    paginator = Paginator(appointments, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    log_action(request.user, 'VIEW', request, "Viewed appointments list")

    return render(request, 'appointments/appointment_list.html', {
        'page_title': 'Appointments',
        'page_obj': page_obj,
        'date_filter': date_filter,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'status_choices': Appointment.STATUS_CHOICES,
        'type_choices': Appointment.TYPE_CHOICES,
        'today': timezone.now().date(),
    })


@login_required
def book_appointment_view(request):
    """Book a new appointment for a patient."""
    if request.method == 'POST':
        patient_id = request.POST.get('patient')
        doctor_id = request.POST.get('doctor')

        patient = get_object_or_404(Patient, id=patient_id)
        doctor = get_object_or_404(User, id=doctor_id, role='doctor')

        appointment = Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            appointment_date=request.POST['appointment_date'],
            appointment_time=request.POST['appointment_time'],
            duration_minutes=int(request.POST.get('duration_minutes', 30)),
            appointment_type=request.POST.get('appointment_type', 'in_person'),
            reason=request.POST.get('reason', '').strip(),
            teleconsult_link=request.POST.get('teleconsult_link', '').strip(),
            booked_by=request.user,
        )

        log_action(request.user, 'CREATE', request,
                   f"Booked appointment for {patient.hospital_number} with Dr. {doctor.get_full_name()}")
        messages.success(request, f"Appointment booked for {patient.full_name} on {appointment.appointment_date}.")
        return redirect('appointments:list')

    patients = Patient.objects.filter(is_active=True).order_by('first_name')
    doctors = User.objects.filter(role='doctor', is_active=True)

    return render(request, 'appointments/book_appointment.html', {
        'page_title': 'Book Appointment',
        'patients': patients,
        'doctors': doctors,
    })


@login_required
def appointment_detail_view(request, pk):
    """View a single appointment with teleconsult join button if approved."""
    appointment = get_object_or_404(Appointment, pk=pk)

    # Patient can only view their own appointment
    if request.user.is_patient_user:
        if not hasattr(request.user, 'patient_profile') or \
           request.user.patient_profile != appointment.patient:
            messages.error(request, "Access denied.")
            return redirect('patients:dashboard')

    log_action(request.user, 'VIEW', request, f"Viewed appointment #{pk}")

    return render(request, 'appointments/appointment_detail.html', {
        'page_title': 'Appointment Details',
        'appointment': appointment,
    })


@login_required
def update_appointment_status_view(request, pk):
    """Update appointment status (doctor/admin only)."""
    if not (request.user.is_doctor or request.user.is_admin_staff):
        messages.error(request, "Permission denied.")
        return redirect('appointments:list')

    appointment = get_object_or_404(Appointment, pk=pk)

    if request.method == 'POST':
        new_status = request.POST.get('status')
        notes = request.POST.get('notes', '').strip()

        if new_status in dict(Appointment.STATUS_CHOICES):
            appointment.status = new_status
        if notes:
            appointment.notes = notes

        # Handle teleconsult link update
        link = request.POST.get('teleconsult_link', '').strip()
        if link:
            appointment.teleconsult_link = link

        appointment.save()
        log_action(request.user, 'UPDATE', request,
                   f"Updated appointment #{pk} status to '{new_status}'")
        messages.success(request, "Appointment updated.")

    return redirect('appointments:detail', pk=pk)


@login_required
def approve_teleconsult_view(request, pk):
    """
    Doctor/admin approves teleconsult access for patient.
    Only after this approval can the patient click the Join link.
    """
    if not request.user.can_approve_teleconsult:
        messages.error(request, "Only doctors can approve teleconsult access.")
        return redirect('appointments:detail', pk=pk)

    appointment = get_object_or_404(Appointment, pk=pk)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve':
            appointment.teleconsult_approved = True
            appointment.teleconsult_approved_by = request.user
            appointment.teleconsult_approved_at = timezone.now()
            appointment.allow_recording = request.POST.get('allow_recording') == 'on'
            appointment.save()
            log_action(request.user, 'APPROVE', request,
                       f"Approved teleconsult for appointment #{pk} — patient {appointment.patient.hospital_number}")
            messages.success(request, "Teleconsult approved. Patient can now join.")

        elif action == 'revoke':
            appointment.teleconsult_approved = False
            appointment.teleconsult_approved_by = None
            appointment.teleconsult_approved_at = None
            appointment.save()
            log_action(request.user, 'REVOKE', request,
                       f"Revoked teleconsult for appointment #{pk}")
            messages.warning(request, "Teleconsult access revoked.")

    return redirect('appointments:detail', pk=pk)


@login_required
def join_teleconsult_view(request, pk):
    """
    Patient joins teleconsult. Only works if teleconsult_approved=True.
    Logs the join event with timestamp.
    """
    appointment = get_object_or_404(Appointment, pk=pk)

    # ── Authorization check ───────────────────────────────────────────────────
    # Patients: must be the patient on this appointment
    if request.user.is_patient_user:
        if not hasattr(request.user, 'patient_profile') or \
           request.user.patient_profile != appointment.patient:
            messages.error(request, "This appointment is not yours.")
            return redirect('patients:dashboard')

    # Check teleconsult is approved
    if not appointment.can_join_teleconsult:
        messages.error(request,
                       "Teleconsult has not been approved yet. "
                       "Please wait for your doctor to authorize the session.")
        return redirect('appointments:detail', pk=pk)

    # Check link exists
    if not appointment.teleconsult_link:
        messages.error(request, "No teleconsult link has been set for this appointment.")
        return redirect('appointments:detail', pk=pk)

    log_action(request.user, 'TELECONSULT', request,
               f"Joined teleconsult for appointment #{pk} — link: {appointment.teleconsult_link}")

    # Redirect to the actual Zoom/Meet link
    return redirect(appointment.teleconsult_link)
