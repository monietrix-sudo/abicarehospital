"""
Management command: send_reminders
Run this every 15 minutes via Windows Task Scheduler or cron:
  python manage.py send_reminders

What it does:
1. Finds medication doses overdue by 30+ minutes and not yet ticked
2. Finds appointments starting in ~24 hours and ~1 hour — sends reminders
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime


class Command(BaseCommand):
    help = 'Send overdue dose alerts and appointment reminders'

    def handle(self, *args, **options):
        self.check_overdue_doses()
        self.send_appointment_reminders()
        self.stdout.write(self.style.SUCCESS('Reminders processed.'))

    def check_overdue_doses(self):
        from apps.medications.models import MedicationDose
        from apps.notifications.utils import notify_dose_overdue
        from apps.notifications.models import Notification

        now = timezone.now()
        cutoff = now - timedelta(minutes=30)

        # Doses that are overdue by 30+ min, not taken, and active schedule
        overdue = MedicationDose.objects.filter(
            scheduled_datetime__lte=cutoff,
            taken=False,
            schedule__is_active=True,
        ).select_related('schedule', 'schedule__patient', 'schedule__prescribed_by')

        for dose in overdue:
            # Avoid duplicate notifications — check if we already notified for this dose
            already = Notification.objects.filter(
                medication_id=dose.schedule_id,
                notif_type='dose_overdue',
                message__contains=dose.scheduled_datetime.strftime('%I:%M %p'),
                created_at__date=now.date(),
            ).exists()
            if not already:
                notify_dose_overdue(dose)
                self.stdout.write(f"  Dose overdue: {dose.schedule.drug_name} for {dose.schedule.patient.full_name}")

    def send_appointment_reminders(self):
        from apps.appointments.models import Appointment
        from apps.notifications.utils import notify_appointment_reminder
        from apps.notifications.models import Notification

        now = timezone.now()

        for hours in [24, 1]:
            window_start = now + timedelta(hours=hours) - timedelta(minutes=10)
            window_end   = now + timedelta(hours=hours) + timedelta(minutes=10)

            appointments = Appointment.objects.filter(
                status__in=['scheduled', 'confirmed'],
            ).select_related('patient', 'doctor', 'patient__user_account')

            for appt in appointments:
                appt_dt = timezone.make_aware(
                    datetime.combine(appt.appointment_date, appt.appointment_time)
                )
                if window_start <= appt_dt <= window_end:
                    # Avoid duplicate reminders
                    already = Notification.objects.filter(
                        appointment_id=appt.pk,
                        notif_type=f'appointment_{hours}hr',
                        created_at__date=now.date(),
                    ).exists()
                    if not already:
                        notify_appointment_reminder(appt, hours)
                        self.stdout.write(f"  Reminder ({hours}hr): {appt}")
