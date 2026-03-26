"""
AbiCare - Patients Views
=========================
Dashboard, patient list, detail, registration, editing.
All views use function-based style with clear comments.
Role-based access enforced with decorators.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.http import JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator

from .models import Patient
from apps.appointments.models import Appointment
from apps.audit_logs.utils import log_action
from apps.accounts.models import User


def role_required(*roles):
    """
    Decorator: restrict view to users with specified roles.
    Usage: @role_required('doctor', 'admin')
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            if request.user.role not in roles and not request.user.is_superuser:
                messages.error(request, "You do not have permission to access this page.")
                return redirect('patients:dashboard')
            return view_func(request, *args, **kwargs)
        wrapper.__name__ = view_func.__name__
        return wrapper
    return decorator


@login_required
def dashboard_view(request):
    """
    Main dashboard. Shows stats, today's appointments, recent patients.
    Content varies by role (doctor sees their patients, admin sees all).
    """
    user = request.user

    # ── Build stats counts ────────────────────────────────────────────────────
    total_patients = Patient.objects.filter(is_active=True).count()
    today = timezone.now().date()

    # Today's appointments
    today_appointments = Appointment.objects.filter(
        appointment_date=today, status__in=['scheduled', 'confirmed']
    )

    # If doctor, filter to their appointments only
    if user.is_doctor:
        today_appointments = today_appointments.filter(doctor=user)
        recent_patients = Patient.objects.filter(
            assigned_doctor=user, is_active=True
        ).order_by('-created_at')[:5]
    else:
        recent_patients = Patient.objects.filter(is_active=True).order_by('-created_at')[:5]

    # ── Monthly registration trend (last 6 months) ─────────────────────────
    from django.db.models.functions import TruncMonth
    monthly_data = (
        Patient.objects.filter(created_at__gte=timezone.now() - timezone.timedelta(days=180))
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    log_action(user, 'VIEW', request, "Accessed dashboard")

    return render(request, 'patients/dashboard.html', {
        'page_title': 'Dashboard',
        'total_patients': total_patients,
        'today_appointments': today_appointments[:8],
        'today_appt_count': today_appointments.count(),
        'recent_patients': recent_patients,
        'monthly_data': list(monthly_data),
        'today': today,
    })


@login_required
def patient_list_view(request):
    """
    Patient list with search and filtering.
    Supports quick search via name, hospital number, phone.
    """
    query = request.GET.get('q', '').strip()
    gender_filter = request.GET.get('gender', '')
    blood_group_filter = request.GET.get('blood_group', '')
    doctor_filter = request.GET.get('doctor', '')

    # ── Base queryset ──────────────────────────────────────────────────────────
    patients = Patient.objects.filter(is_active=True).select_related('assigned_doctor')

    # Doctors see only their own patients; admin/superuser/others see all
    if request.user.is_doctor and not request.user.is_admin_staff:
        patients = patients.filter(assigned_doctor=request.user)

    # ── Apply search ──────────────────────────────────────────────────────────
    if query:
        patients = patients.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(middle_name__icontains=query) |
            Q(hospital_number__icontains=query) |
            Q(phone_number__icontains=query) |
            Q(email__icontains=query)
        )

    # ── Apply filters ─────────────────────────────────────────────────────────
    if gender_filter:
        patients = patients.filter(gender=gender_filter)
    if blood_group_filter:
        patients = patients.filter(blood_group=blood_group_filter)
    if doctor_filter:
        patients = patients.filter(assigned_doctor_id=doctor_filter)

    total_results = patients.count()

    # ── Pagination (20 per page) ───────────────────────────────────────────────
    paginator = Paginator(patients.order_by('-created_at'), 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Doctors for filter dropdown
    doctors = User.objects.filter(role='doctor', is_active=True)

    log_action(request.user, 'VIEW', request, f"Viewed patient list. Query: '{query}'")

    return render(request, 'patients/patient_list.html', {
        'page_title': 'Patients',
        'page_obj': page_obj,
        'query': query,
        'gender_filter': gender_filter,
        'blood_group_filter': blood_group_filter,
        'doctor_filter': doctor_filter,
        'doctors': doctors,
        'total_results': total_results,
    })


@login_required
def patient_detail_view(request, hospital_number):
    """
    Full patient profile: personal info, medical history, records, appointments.
    Tabs: Overview | Records | Lab Results | Medications | Appointments
    """
    patient = get_object_or_404(Patient, hospital_number=hospital_number)

    # Fetch related data for tabs
    from apps.records.models import MedicalRecord
    from apps.lab_results.models import LabResult
    from apps.medications.models import MedicationSchedule

    records      = MedicalRecord.objects.filter(patient=patient).order_by('-uploaded_at')[:10]
    lab_results  = LabResult.objects.filter(patient=patient).order_by('-result_date')[:10]
    medications  = MedicationSchedule.objects.filter(patient=patient, is_active=True)
    appointments = Appointment.objects.filter(patient=patient).order_by('-appointment_date')[:10]

    # Pass counts separately — sliced querysets have no .count() in templates
    records_count      = MedicalRecord.objects.filter(patient=patient).count()
    lab_results_count  = LabResult.objects.filter(patient=patient).count()
    medications_count  = MedicationSchedule.objects.filter(patient=patient, is_active=True).count()
    appointments_count = Appointment.objects.filter(patient=patient).count()

    log_action(request.user, 'VIEW', request, f"Viewed patient profile: {patient.hospital_number}")

    return render(request, 'patients/patient_detail.html', {
        'page_title':        f"Patient: {patient.full_name}",
        'patient':           patient,
        'records':           records,
        'lab_results':       lab_results,
        'medications':       medications,
        'appointments':      appointments,
        'records_count':     records_count,
        'lab_results_count': lab_results_count,
        'medications_count': medications_count,
        'appointments_count': appointments_count,
    })


@login_required
@role_required('admin', 'receptionist', 'doctor', 'nurse')
def add_patient_view(request):
    """
    Register a new patient. Generates hospital number automatically.
    """
    if request.method == 'POST':
        # Validate required fields first
        required = ['first_name', 'last_name', 'date_of_birth', 'gender', 'phone_number']
        missing = [f for f in required if not request.POST.get(f, '').strip()]
        if missing:
            messages.error(request, f"Required fields missing: {', '.join(missing)}")
            doctors = User.objects.filter(role='doctor', is_active=True)
            return render(request, 'patients/add_patient.html', {
                'page_title': 'Register New Patient',
                'doctors': doctors,
                'form_data': request.POST,
            })

        # ── Generate hospital number ──────────────────────────────────────────
        year = timezone.now().year
        last_patient = Patient.objects.filter(
            hospital_number__startswith=f'ABI-{year}-'
        ).order_by('-hospital_number').first()

        if last_patient:
            try:
                seq = int(last_patient.hospital_number.split('-')[-1]) + 1
            except (ValueError, IndexError):
                seq = Patient.objects.filter(
                    hospital_number__startswith=f'ABI-{year}-'
                ).count() + 1
        else:
            seq = 1

        hospital_number = f"ABI-{year}-{str(seq).zfill(5)}"

        try:
            # ── Create patient ────────────────────────────────────────────────
            patient = Patient(
                hospital_number=hospital_number,
                first_name=request.POST['first_name'].strip(),
                middle_name=request.POST.get('middle_name', '').strip(),
                last_name=request.POST['last_name'].strip(),
                date_of_birth=request.POST['date_of_birth'],
                gender=request.POST['gender'],
                phone_number=request.POST['phone_number'].strip(),
                alt_phone_number=request.POST.get('alt_phone_number', '').strip(),
                email=request.POST.get('email', '').strip(),
                address=request.POST.get('address', '').strip(),
                city=request.POST.get('city', '').strip(),
                state=request.POST.get('state', '').strip(),
                blood_group=request.POST.get('blood_group', ''),
                genotype=request.POST.get('genotype', ''),
                allergies=request.POST.get('allergies', '').strip(),
                chronic_conditions=request.POST.get('chronic_conditions', '').strip(),
                marital_status=request.POST.get('marital_status', ''),
                occupation=request.POST.get('occupation', '').strip(),
                nationality=request.POST.get('nationality', 'Nigerian').strip(),
                state_of_origin=request.POST.get('state_of_origin', '').strip(),
                nok_name=request.POST.get('nok_name', '').strip(),
                nok_relationship=request.POST.get('nok_relationship', '').strip(),
                nok_phone=request.POST.get('nok_phone', '').strip(),
                nok_address=request.POST.get('nok_address', '').strip(),
                registered_by=request.user,
                is_active=True,
                legacy_hospital_number=request.POST.get('legacy_hospital_number','').strip(),
            )

            # Assign doctor if selected
            doctor_id = request.POST.get('assigned_doctor')
            if doctor_id:
                try:
                    patient.assigned_doctor_id = int(doctor_id)
                except (ValueError, TypeError):
                    pass

            # Handle photo upload
            if 'photo' in request.FILES:
                patient.photo = request.FILES['photo']

            patient.full_clean()   # run model validation before save
            patient.save()

            log_action(request.user, 'CREATE', request, f"Registered new patient: {hospital_number}")
            messages.success(request, f"✓ Patient {patient.full_name} registered. ID: {hospital_number}")
            return redirect('patient_detail:detail', hospital_number=hospital_number)

        except Exception as e:
            messages.error(request, f"Registration failed: {str(e)}")

    # GET - show empty form
    doctors = User.objects.filter(role='doctor', is_active=True)
    return render(request, 'patients/add_patient.html', {
        'page_title': 'Register New Patient',
        'doctors': doctors,
        'form_data': {},
    })


@login_required
@role_required('admin', 'receptionist', 'doctor', 'nurse')
def edit_patient_view(request, hospital_number):
    """Update patient information."""
    patient = get_object_or_404(Patient, hospital_number=hospital_number)

    if request.method == 'POST':
        # Update all editable fields
        patient.first_name = request.POST.get('first_name', patient.first_name).strip()
        patient.middle_name = request.POST.get('middle_name', patient.middle_name).strip()
        patient.last_name = request.POST.get('last_name', patient.last_name).strip()
        patient.phone_number = request.POST.get('phone_number', patient.phone_number).strip()
        patient.alt_phone_number = request.POST.get('alt_phone_number', '').strip()
        patient.email = request.POST.get('email', '').strip()
        patient.address = request.POST.get('address', '').strip()
        patient.city = request.POST.get('city', '').strip()
        patient.state = request.POST.get('state', '').strip()
        patient.blood_group = request.POST.get('blood_group', '')
        patient.genotype = request.POST.get('genotype', '')
        patient.allergies = request.POST.get('allergies', '').strip()
        patient.chronic_conditions = request.POST.get('chronic_conditions', '').strip()
        patient.occupation = request.POST.get('occupation', '').strip()
        patient.nok_name = request.POST.get('nok_name', '').strip()
        patient.nok_relationship = request.POST.get('nok_relationship', '').strip()
        patient.nok_phone = request.POST.get('nok_phone', '').strip()
        patient.nok_address = request.POST.get('nok_address', '').strip()

        # Update assigned doctor
        doctor_id = request.POST.get('assigned_doctor')
        if doctor_id:
            patient.assigned_doctor_id = doctor_id

        # Update photo if new one uploaded
        if 'photo' in request.FILES:
            patient.photo = request.FILES['photo']

        patient.save()
        log_action(request.user, 'UPDATE', request, f"Updated patient: {patient.hospital_number}")
        messages.success(request, "Patient record updated successfully.")
        return redirect('patient_detail:detail', hospital_number=hospital_number)

    doctors = User.objects.filter(role='doctor', is_active=True)
    return render(request, 'patients/edit_patient.html', {
        'page_title': f"Edit: {patient.full_name}",
        'patient': patient,
        'doctors': doctors,
    })


@login_required
def quick_search_api(request):
    """
    AJAX endpoint for quick patient search (used in search bar autocomplete).
    Returns JSON list of matching patients.
    """
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    patients = Patient.objects.filter(
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(hospital_number__icontains=query) |
        Q(phone_number__icontains=query),
        is_active=True
    )[:8]   # Limit to 8 suggestions

    results = [
        {
            'id': str(p.patient_id),
            'name': p.full_name,
            'hospital_number': p.hospital_number,
            'age': p.age,
            'gender': p.get_gender_display(),
            'url': f"/patients/{p.hospital_number}/",
            'photo': p.photo.url if p.photo else None,
        }
        for p in patients
    ]

    return JsonResponse({'results': results})


@login_required
@role_required('admin', 'receptionist', 'doctor')
def deactivate_patient_view(request, hospital_number):
    """
    Soft-delete a patient — sets is_active=False.
    The record is NEVER permanently deleted (medical data must be retained).
    Only admin, receptionist, or doctor can do this.
    Requires POST + password confirmation to prevent accidents.
    """
    patient = get_object_or_404(Patient, hospital_number=hospital_number)

    if request.method == 'POST':
        # Require password re-entry as a safety check
        from django.contrib.auth import authenticate
        password = request.POST.get('confirm_password', '')
        user = authenticate(request, username=request.user.username, password=password)

        if user is None:
            messages.error(request, "Incorrect password. Patient was NOT removed.")
            return redirect('patient_detail:detail', hospital_number=hospital_number)

        reason = request.POST.get('reason', '').strip()

        patient.is_active = False
        patient.save()

        log_action(
            request.user, 'DELETE', request,
            f"Deactivated patient {hospital_number} ({patient.full_name}). Reason: {reason or 'Not provided'}"
        )
        messages.success(
            request,
            f"Patient {patient.full_name} has been removed from the active list. "
            f"Their medical records are retained."
        )
        return redirect('patient_detail:list')

    # GET — should not happen (form is in the modal), redirect back
    return redirect('patient_detail:detail', hospital_number=hospital_number)
