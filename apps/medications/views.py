"""
AbiCare - Medications Views
=============================
Doctors prescribe medications with timetables.
Patients tick off doses as taken from their portal.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta, datetime, time

from .models import MedicationSchedule, MedicationDose
from apps.patients.models import Patient
from apps.audit_logs.utils import log_action


# ── Helper: generate dose times based on frequency ────────────────────────────
FREQUENCY_TIMES = {
    'once':   [time(8, 0)],
    'twice':  [time(8, 0), time(20, 0)],
    'thrice': [time(8, 0), time(14, 0), time(20, 0)],
    'four':   [time(7, 0), time(12, 0), time(17, 0), time(22, 0)],
    'weekly': [time(8, 0)],
    'as_needed': [],  # no automatic doses for PRN medications
}


def generate_doses(schedule):
    """
    Auto-generate MedicationDose entries for a schedule.
    Called after creating a MedicationSchedule.
    """
    times = FREQUENCY_TIMES.get(schedule.frequency, [time(8, 0)])
    if not times:
        return  # PRN - no doses to generate

    current_date = schedule.start_date
    end_date = schedule.end_date

    # Weekly: step 7 days; others: step 1 day
    step_days = 7 if schedule.frequency == 'weekly' else 1

    doses_to_create = []
    while current_date <= end_date:
        for dose_time in times:
            scheduled_dt = datetime.combine(current_date, dose_time)
            # Make timezone-aware
            scheduled_dt = timezone.make_aware(scheduled_dt)
            doses_to_create.append(
                MedicationDose(
                    schedule=schedule,
                    scheduled_datetime=scheduled_dt,
                )
            )
        current_date += timedelta(days=step_days)

    MedicationDose.objects.bulk_create(doses_to_create)


@login_required
def prescribe_medication_view(request, patient_hospital_number):
    """
    Doctor prescribes a medication for a patient.
    Auto-generates dose timetable on save.
    """
    if not (request.user.is_doctor or request.user.is_admin_staff):
        messages.error(request, "Only doctors can prescribe medications.")
        return redirect('patients:dashboard')

    patient = get_object_or_404(Patient, hospital_number=patient_hospital_number)

    if request.method == 'POST':
        schedule = MedicationSchedule.objects.create(
            patient=patient,
            prescribed_by=request.user,
            drug_name=request.POST['drug_name'].strip(),
            dosage=request.POST['dosage'].strip(),
            frequency=request.POST['frequency'],
            route=request.POST.get('route', 'oral'),
            start_date=request.POST['start_date'],
            end_date=request.POST['end_date'],
            instructions=request.POST.get('instructions', '').strip(),
        )

        # Auto-generate the dose timetable
        generate_doses(schedule)

        log_action(request.user, 'CREATE', request,
                   f"Prescribed {schedule.drug_name} for patient {patient.hospital_number}")
        messages.success(request,
                         f"Prescription for {schedule.drug_name} created. "
                         f"Timetable generated.")
        return redirect('patient_detail:detail', hospital_number=patient_hospital_number)

    return render(request, 'medications/prescribe.html', {
        'page_title': 'Prescribe Medication',
        'patient': patient,
        'frequency_choices': MedicationSchedule.FREQUENCY_CHOICES,
        'route_choices': MedicationSchedule.ROUTE_CHOICES,
        'today': timezone.now().date(),
    })


@login_required
def medication_timetable_view(request, schedule_id):
    """
    Shows the full dose timetable for a medication schedule.
    Patients see this to know when to take their meds.
    """
    schedule = get_object_or_404(MedicationSchedule, pk=schedule_id)

    # Patients can only see their own
    if request.user.is_patient_user:
        if not hasattr(request.user, 'patient_profile') or \
                request.user.patient_profile != schedule.patient:
            messages.error(request, "Access denied.")
            return redirect('patients:dashboard')

    doses = schedule.doses.all().order_by('scheduled_datetime')
    today = timezone.now().date()

    log_action(request.user, 'VIEW', request, f"Viewed medication timetable #{schedule_id}")

    return render(request, 'medications/timetable.html', {
        'page_title': f'Medication: {schedule.drug_name}',
        'schedule': schedule,
        'doses': doses,
        'today': today,
    })


@login_required
def tick_dose_view(request, dose_id):
    """
    Patient ticks a dose as taken.
    Only the patient themselves (or staff) can tick their own doses.
    AJAX-friendly: returns JSON if requested via fetch().
    """
    dose = get_object_or_404(MedicationDose, pk=dose_id)

    # Authorization: patient must own this dose
    if request.user.is_patient_user:
        if not hasattr(request.user, 'patient_profile') or \
                request.user.patient_profile != dose.schedule.patient:
            messages.error(request, "Access denied.")
            return redirect('patients:dashboard')

    if dose.taken:
        messages.info(request, "This dose is already marked as taken.")
    else:
        dose.mark_taken()
        log_action(request.user, 'UPDATE', request,
                   f"Patient ticked dose #{dose_id} ({dose.schedule.drug_name}) as taken")
        messages.success(request,
                         f"✔ {dose.schedule.drug_name} dose marked as taken at "
                         f"{dose.taken_at.strftime('%I:%M %p')}.")

    return redirect('medications:timetable', schedule_id=dose.schedule_id)


@login_required
def patient_medications_view(request):
    """
    Patient dashboard: see all their active medication schedules.
    """
    if request.user.is_patient_user and hasattr(request.user, 'patient_profile'):
        patient = request.user.patient_profile
    else:
        # Staff viewing all medications
        patient = None

    schedules = MedicationSchedule.objects.select_related('prescribed_by', 'patient')

    if patient:
        schedules = schedules.filter(patient=patient, is_active=True)
    else:
        patient_hn = request.GET.get('patient', '')
        if patient_hn:
            schedules = schedules.filter(patient__hospital_number=patient_hn)

    return render(request, 'medications/medication_list.html', {
        'page_title': 'Medications',
        'schedules': schedules,
    })
