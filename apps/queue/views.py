from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import QueueEntry
from apps.patients.models import Patient
from apps.accounts.models import User
from apps.appointments.models import Appointment
from apps.audit_logs.utils import log_action


@login_required
def queue_view(request):
    today   = timezone.now().date()
    entries = QueueEntry.objects.filter(queue_date=today).select_related(
        'patient', 'doctor', 'called_by'
    )
    waiting_count  = entries.filter(status='waiting').count()
    called_count   = entries.filter(status='called').count()
    done_count     = entries.filter(status='done').count()
    doctors        = User.objects.filter(role='doctor', is_active=True)
    patients       = Patient.objects.filter(is_active=True).order_by('first_name')

    return render(request, 'queue/queue.html', {
        'page_title':    'Waiting Room',
        'entries':       entries,
        'today':         today,
        'waiting_count': waiting_count,
        'called_count':  called_count,
        'done_count':    done_count,
        'doctors':       doctors,
        'patients':      patients,
    })


@login_required
def add_to_queue_view(request):
    if request.method != 'POST':
        return redirect('queue:list')

    patient_id = request.POST.get('patient_id')
    doctor_id  = request.POST.get('doctor_id')
    appt_id    = request.POST.get('appointment_id')
    notes      = request.POST.get('notes', '').strip()

    if not patient_id:
        messages.error(request, "Please select a patient.")
        return redirect('queue:list')

    patient = get_object_or_404(Patient, pk=patient_id)
    today   = timezone.now().date()

    # Check not already in today's queue
    if QueueEntry.objects.filter(patient=patient, queue_date=today,
                                  status__in=['waiting','called','with_doctor']).exists():
        messages.warning(request, f"{patient.full_name} is already in today's queue.")
        return redirect('queue:list')

    entry = QueueEntry(
        patient=patient,
        queue_date=today,
        queue_number=QueueEntry.next_number_for_today(),
        notes=notes,
        added_by=request.user,
    )
    if doctor_id:
        entry.doctor_id = doctor_id
    if appt_id:
        entry.appointment_id = appt_id

    entry.save()
    log_action(request.user, 'CREATE', request,
               f"Added {patient.full_name} to queue as #{entry.queue_number}")
    messages.success(request, f"{patient.full_name} added to queue — Number #{entry.queue_number}")
    return redirect('queue:list')


@login_required
def call_patient_view(request, pk):
    entry          = get_object_or_404(QueueEntry, pk=pk)
    entry.status   = 'called'
    entry.called_at = timezone.now()
    entry.called_by = request.user
    entry.save()
    log_action(request.user, 'UPDATE', request,
               f"Called queue #{entry.queue_number}: {entry.patient.full_name}")
    messages.success(request, f"Called #{entry.queue_number} — {entry.patient.full_name}")
    return redirect('queue:list')


@login_required
def update_status_view(request, pk):
    if request.method != 'POST':
        return redirect('queue:list')
    entry = get_object_or_404(QueueEntry, pk=pk)
    entry.status = request.POST.get('status', entry.status)
    entry.save()
    return redirect('queue:list')


def display_board_view(request):
    """Public display board — no login needed (for TV/monitor in waiting room)."""
    today   = timezone.now().date()
    entries = QueueEntry.objects.filter(
        queue_date=today, status__in=['waiting','called']
    ).select_related('patient', 'doctor')[:20]
    return render(request, 'queue/display_board.html', {
        'entries': entries,
        'now':     timezone.now(),
    })


def self_checkin_view(request):
    """Patient self-check-in via tablet/kiosk. Searches by hospital number."""
    if request.method == 'POST':
        hospital_number = request.POST.get('hospital_number', '').strip().upper()
        try:
            patient = Patient.objects.get(
                hospital_number=hospital_number, is_active=True
            )
            today = timezone.now().date()

            if QueueEntry.objects.filter(
                patient=patient, queue_date=today,
                status__in=['waiting','called','with_doctor']
            ).exists():
                entry = QueueEntry.objects.get(patient=patient, queue_date=today)
                return render(request, 'queue/self_checkin.html', {
                    'already_checked_in': True,
                    'entry': entry,
                })

            entry = QueueEntry.objects.create(
                patient=patient,
                queue_date=today,
                queue_number=QueueEntry.next_number_for_today(),
                self_checkin=True,
                added_by=None,
            )
            return render(request, 'queue/self_checkin.html', {
                'success': True,
                'entry':   entry,
                'patient': patient,
            })

        except Patient.DoesNotExist:
            return render(request, 'queue/self_checkin.html', {
                'error': 'Patient not found. Please check your hospital number and try again.',
            })

    return render(request, 'queue/self_checkin.html', {})


def queue_status_api(request):
    """AJAX endpoint — returns current queue state for live updates."""
    today   = timezone.now().date()
    entries = QueueEntry.objects.filter(
        queue_date=today
    ).select_related('patient','doctor').values(
        'id','queue_number','status',
        'patient__first_name','patient__last_name',
        'doctor__first_name','doctor__last_name',
        'called_at','check_in_time',
    )
    data = []
    for e in entries:
        data.append({
            'id':           e['id'],
            'number':       e['queue_number'],
            'status':       e['status'],
            'patient':      f"{e['patient__first_name']} {e['patient__last_name']}",
            'doctor':       f"Dr. {e['doctor__first_name']} {e['doctor__last_name']}"
                            if e['doctor__first_name'] else '—',
            'check_in':     e['check_in_time'].strftime('%H:%M') if e['check_in_time'] else '—',
        })
    return JsonResponse({'entries': data, 'time': timezone.now().strftime('%H:%M:%S')})
