"""
AbiCare - Notification Utilities
===================================
Twilio is completely optional.
If TWILIO_* settings are missing or empty, WhatsApp is silently skipped
and only email + in-app notifications are sent.
The system never crashes due to missing Twilio config.
"""

from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import Notification, NotificationPreference


def send_notification(user, notif_type, title, message, link='',
                      patient_id=None, appointment_id=None, medication_id=None):
    """
    Central dispatcher — sends in-app + email + WhatsApp (if configured).
    Gracefully skips any channel that is not available or not configured.
    """
    prefs, _ = NotificationPreference.objects.get_or_create(user=user)

    # ── In-app notification ───────────────────────────────────────────
    if prefs.inapp_enabled:
        Notification.objects.create(
            user=user,
            notif_type=notif_type,
            title=title,
            message=message,
            link=link,
            patient_id=patient_id,
            appointment_id=appointment_id,
            medication_id=medication_id,
        )

    # ── Email via Gmail SMTP ──────────────────────────────────────────
    if prefs.email_enabled and user.email:
        try:
            send_mail(
                subject=f"[{settings.HOSPITAL_NAME}] {title}",
                message=f"{message}\n\n— {settings.HOSPITAL_NAME} EHR System\n{settings.HOSPITAL_WEBSITE}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,   # never crash if email fails
            )
        except Exception:
            pass

    # ── WhatsApp via Twilio (only if configured) ──────────────────────
    if prefs.whatsapp_enabled and prefs.whatsapp_number:
        _try_whatsapp(prefs.whatsapp_number, f"*{title}*\n{message}")


def _try_whatsapp(to_number, message):
    """
    Attempt to send WhatsApp via Twilio.
    Silently does nothing if Twilio is not installed or not configured.
    This means the system works identically with or without Twilio.
    """
    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '').strip()
    auth_token  = getattr(settings, 'TWILIO_AUTH_TOKEN',  '').strip()
    from_number = getattr(settings, 'TWILIO_WHATSAPP_FROM', '').strip()

    # Exit silently if any Twilio credential is missing
    if not account_sid or not auth_token or not from_number:
        return

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        client.messages.create(
            from_=f'whatsapp:{from_number}',
            to=f'whatsapp:{to_number}',
            body=message,
        )
    except ImportError:
        # twilio package not installed — that's fine, skip silently
        pass
    except Exception:
        # Any Twilio API error — skip silently, never crash the app
        pass


def notify_dose_overdue(dose):
    from apps.accounts.models import User
    schedule = dose.schedule
    patient  = schedule.patient

    msg = (
        f"Patient {patient.full_name} ({patient.hospital_number}) missed their "
        f"{dose.scheduled_datetime.strftime('%I:%M %p')} dose of "
        f"{schedule.drug_name} {schedule.dosage}."
    )

    if schedule.prescribed_by:
        send_notification(
            user=schedule.prescribed_by,
            notif_type='dose_overdue',
            title=f"Missed Dose — {patient.full_name}",
            message=msg,
            link=f"/medications/schedule/{schedule.pk}/",
            patient_id=patient.pk,
            medication_id=schedule.pk,
        )

    for nurse in User.objects.filter(role='nurse', is_active=True):
        send_notification(
            user=nurse,
            notif_type='dose_overdue',
            title=f"Missed Dose — {patient.full_name}",
            message=msg,
            link=f"/medications/schedule/{schedule.pk}/",
            patient_id=patient.pk,
            medication_id=schedule.pk,
        )


def notify_appointment_reminder(appointment, hours_before):
    patient  = appointment.patient
    doctor   = appointment.doctor
    label    = "tomorrow" if hours_before == 24 else "in 1 hour"
    time_str = appointment.appointment_time.strftime('%I:%M %p')
    date_str = appointment.appointment_date.strftime('%B %d, %Y')
    doc_name = f"Dr. {doctor.get_full_name()}" if doctor else "your doctor"

    if doctor:
        send_notification(
            user=doctor,
            notif_type=f'appointment_{hours_before}hr',
            title=f"Appointment Reminder — {patient.full_name}",
            message=f"{patient.full_name} has a {appointment.get_appointment_type_display()} appointment on {date_str} at {time_str} ({label}).",
            link=f"/appointments/{appointment.pk}/",
            patient_id=patient.pk,
            appointment_id=appointment.pk,
        )

    if patient.user_account:
        send_notification(
            user=patient.user_account,
            notif_type=f'appointment_{hours_before}hr',
            title="Appointment Reminder",
            message=f"You have a {appointment.get_appointment_type_display()} with {doc_name} on {date_str} at {time_str} ({label}).",
            link=f"/appointments/{appointment.pk}/",
            appointment_id=appointment.pk,
        )
