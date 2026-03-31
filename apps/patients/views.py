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
    OPTIMISED: Uses .only() to fetch only columns shown in the list,
    not the full row (avoids loading allergies, address, etc. for every patient).
    """
    query              = request.GET.get('q', '').strip()
    gender_filter      = request.GET.get('gender', '')
    blood_group_filter = request.GET.get('blood_group', '')
    doctor_filter      = request.GET.get('doctor', '')

    # Fetch only the columns displayed in the list — massive RAM/speed saving
    patients = Patient.objects.filter(is_active=True).select_related(
        'assigned_doctor'
    ).only(
        'patient_id', 'hospital_number', 'first_name', 'middle_name', 'last_name',
        'date_of_birth', 'gender', 'phone_number', 'blood_group',
        'created_at', 'has_pending_fields',
        'assigned_doctor__first_name', 'assigned_doctor__last_name',
    )

    if request.user.is_doctor and not request.user.is_admin_staff:
        patients = patients.filter(assigned_doctor=request.user)

    if query:
        patients = patients.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)  |
            Q(middle_name__icontains=query)|
            Q(hospital_number__icontains=query) |
            Q(phone_number__icontains=query)    |
            Q(email__icontains=query)
        )

    if gender_filter:      patients = patients.filter(gender=gender_filter)
    if blood_group_filter: patients = patients.filter(blood_group=blood_group_filter)
    if doctor_filter:      patients = patients.filter(assigned_doctor_id=doctor_filter)

    total_results = patients.count()

    paginator   = Paginator(patients.order_by('-created_at'), 20)
    page_obj    = paginator.get_page(request.GET.get('page', 1))
    doctors     = User.objects.filter(role='doctor', is_active=True).only(
        'pk', 'first_name', 'last_name'
    )

    log_action(request.user, 'VIEW', request,
               f"Viewed patient list. Query: '{query}'")

    return render(request, 'patients/patient_list.html', {
        'page_title':         'Patients',
        'page_obj':           page_obj,
        'query':              query,
        'gender_filter':      gender_filter,
        'blood_group_filter': blood_group_filter,
        'doctor_filter':      doctor_filter,
        'doctors':            doctors,
        'total_results':      total_results,
    })


@login_required
def patient_detail_view(request, hospital_number):
    """
    Full patient profile: personal info, medical history, records, appointments.
    OPTIMISED: Uses select_related + prefetch_related to reduce DB queries.
    Also fetches family memberships for the Convert to Family button.
    """
    patient = get_object_or_404(
        Patient.objects.select_related(
            'assigned_doctor',
            'registered_by',
            'user_account',
        ),
        hospital_number=hospital_number
    )

    # Prefetch all family memberships in one query
    family_memberships = patient.family_memberships.filter(
        is_active=True
    ).select_related('family').order_by('family__family_name')

    from apps.records.models import MedicalRecord
    from apps.lab_results.models import LabResult
    from apps.medications.models import MedicationSchedule

    # All fetched in single queries with select_related to avoid N+1
    records = MedicalRecord.objects.filter(
        patient=patient, is_deleted=False
    ).select_related('uploaded_by').order_by('-uploaded_at')[:10]

    lab_results = LabResult.objects.filter(
        patient=patient
    ).select_related('template').order_by('-ordered_at')[:10]

    medications = MedicationSchedule.objects.filter(
        patient=patient, is_active=True
    ).order_by('drug_name')

    appointments = Appointment.objects.filter(
        patient=patient
    ).select_related('doctor').order_by('-appointment_date')[:10]

    # Single aggregated count query instead of 4 separate .count() calls
    from django.db.models import Count, Q
    counts = Patient.objects.filter(pk=patient.pk).aggregate(
        records_count=Count('medicalrecord', filter=Q(medicalrecord__is_deleted=False)),
        lab_results_count=Count('labresult'),
        medications_count=Count('medicationschedule', filter=Q(medicationschedule__is_active=True)),
        appointments_count=Count('appointment'),
    )

    log_action(request.user, 'VIEW', request,
               f"Viewed patient profile: {patient.hospital_number}")

    return render(request, 'patients/patient_detail.html', {
        'page_title':         f"Patient: {patient.full_name}",
        'patient':            patient,
        'family_memberships': family_memberships,
        'records':            records,
        'lab_results':        lab_results,
        'medications':        medications,
        'appointments':       appointments,
        'records_count':      counts['records_count'],
        'lab_results_count':  counts['lab_results_count'],
        'medications_count':  counts['medications_count'],
        'appointments_count': counts['appointments_count'],
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
            # ── Create patient with all EHR-standard fields ───────────────────
            def g(field, default=''):
                return request.POST.get(field, default).strip()

            patient = Patient(
                hospital_number=hospital_number,
                first_name=request.POST['first_name'].strip(),
                middle_name=g('middle_name'),
                preferred_name=g('preferred_name'),
                last_name=request.POST['last_name'].strip(),
                date_of_birth=request.POST['date_of_birth'],
                gender=request.POST['gender'],
                phone_number=request.POST['phone_number'].strip(),
                alt_phone_number=g('alt_phone_number'),
                email=g('email'),
                marital_status=g('marital_status'),
                religion=g('religion'),
                occupation=g('occupation'),
                primary_language=g('primary_language'),
                address=g('address'),
                city=g('city'),
                state=g('state'),
                lga=g('lga'),
                hometown=g('hometown'),
                state_of_origin=g('state_of_origin'),
                nationality=g('nationality') or 'Nigerian',
                disabilities=g('disabilities'),
                blood_group=g('blood_group'),
                genotype=g('genotype'),
                allergies=g('allergies'),
                chronic_conditions=g('chronic_conditions'),
                nok_name=g('nok_name'),
                nok_relationship=g('nok_relationship'),
                nok_phone=g('nok_phone'),
                nok_alt_phone=g('nok_alt_phone'),
                nok_address=g('nok_address'),
                nok_email=g('nok_email'),
                nok_occupation=g('nok_occupation'),
                insurance_provider=g('insurance_provider'),
                insurance_number=g('insurance_number'),
                nhis_number=g('nhis_number'),
                hmo_name=g('hmo_name'),
                ward=g('ward'),
                registered_by=request.user,
                is_active=True,
                legacy_hospital_number=g('legacy_hospital_number'),
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
    """
    Update every field on a patient record.
    Age is auto-calculated from date_of_birth — editing DOB updates age automatically.
    PENDING values are cleared when a real value is entered.
    """
    patient = get_object_or_404(Patient, hospital_number=hospital_number)

    if request.method == 'POST':
        def g(field, default=''):
            return request.POST.get(field, default).strip()

        # ── Core Identity ─────────────────────────────────────────────
        patient.first_name     = g('first_name') or patient.first_name
        patient.middle_name    = g('middle_name')
        patient.preferred_name = g('preferred_name')
        patient.last_name      = g('last_name') or patient.last_name
        patient.gender         = g('gender') or patient.gender
        patient.marital_status = g('marital_status')
        patient.religion       = g('religion')
        patient.occupation     = g('occupation')
        patient.primary_language = g('primary_language')

        # DOB — editing this automatically updates age (age is a @property)
        dob_raw = g('date_of_birth')
        if dob_raw:
            try:
                from datetime import datetime
                patient.date_of_birth = datetime.strptime(dob_raw, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, f"Invalid date format: {dob_raw}. Use YYYY-MM-DD.")
                doctors = User.objects.filter(role='doctor', is_active=True)
                return render(request, 'patients/edit_patient.html', {
                    'page_title': f"Edit: {patient.full_name}",
                    'patient': patient,
                    'doctors': doctors,
                })

        # ── Contact ───────────────────────────────────────────────────
        patient.phone_number     = g('phone_number') or patient.phone_number
        patient.alt_phone_number = g('alt_phone_number')
        patient.email            = g('email')
        patient.address          = g('address')
        patient.city             = g('city')
        patient.state            = g('state')
        patient.lga              = g('lga')
        patient.hometown         = g('hometown')

        # ── Origin ────────────────────────────────────────────────────
        patient.state_of_origin = g('state_of_origin')
        patient.nationality     = g('nationality') or 'Nigerian'
        patient.disabilities    = g('disabilities')

        # ── Medical ───────────────────────────────────────────────────
        patient.blood_group        = g('blood_group')
        patient.genotype           = g('genotype')
        patient.allergies          = g('allergies')
        patient.chronic_conditions = g('chronic_conditions')
        patient.ward               = g('ward')

        # ── Insurance ─────────────────────────────────────────────────
        patient.insurance_provider = g('insurance_provider')
        patient.insurance_number   = g('insurance_number')
        patient.nhis_number        = g('nhis_number')
        patient.hmo_name           = g('hmo_name')

        # ── Next of Kin ───────────────────────────────────────────────
        patient.nok_name         = g('nok_name')
        patient.nok_relationship = g('nok_relationship')
        patient.nok_phone        = g('nok_phone')
        patient.nok_alt_phone    = g('nok_alt_phone')
        patient.nok_address      = g('nok_address')
        patient.nok_email        = g('nok_email')
        patient.nok_occupation   = g('nok_occupation')

        # ── Previous Record ───────────────────────────────────────────
        patient.legacy_hospital_number = g('legacy_hospital_number')

        # ── Assigned Doctor ───────────────────────────────────────────
        doctor_id = g('assigned_doctor')
        if doctor_id:
            try:
                patient.assigned_doctor_id = int(doctor_id)
            except (ValueError, TypeError):
                patient.assigned_doctor = None
        else:
            patient.assigned_doctor = None

        # ── Photo ─────────────────────────────────────────────────────
        if 'photo' in request.FILES:
            patient.photo = request.FILES['photo']

        # ── Clear PENDING flags for fields that now have real values ──
        if patient.has_pending_fields:
            still_pending = []
            for field in patient.pending_fields:
                val = getattr(patient, field, '')
                if str(val).upper() == 'PENDING' or not val:
                    still_pending.append(field)
            patient.pending_field_list = ','.join(still_pending)
            patient.has_pending_fields = bool(still_pending)

        patient.save()
        log_action(request.user, 'UPDATE', request,
                   f"Updated patient: {patient.hospital_number}")
        messages.success(request,
            f"{patient.full_name} updated successfully.")
        return redirect('patient_detail:detail',
                        hospital_number=hospital_number)

    doctors = User.objects.filter(role='doctor', is_active=True)
    return render(request, 'patients/edit_patient.html', {
        'page_title':         f"Edit Patient — {patient.full_name}",
        'patient':            patient,
        'doctors':            doctors,
        'blood_group_choices': Patient.BLOOD_GROUP_CHOICES,
        'genotype_choices':    Patient.GENOTYPE_CHOICES,
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
