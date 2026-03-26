"""
AbiCare - Medical Records Views
==================================
Supports: upload, view, soft-delete, version history, record sharing.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from datetime import timedelta

from .models import MedicalRecord, RecordVersion, RecordShare
from apps.patients.models import Patient
from apps.appointments.models import Appointment
from apps.audit_logs.utils import log_action


def _detect_file_type(filename):
    name = filename.lower()
    if any(name.endswith(e) for e in ['.jpg','.jpeg','.png','.gif','.webp']):
        return 'image'
    elif name.endswith('.pdf'):
        return 'pdf'
    elif any(name.endswith(e) for e in ['.mp4','.webm','.ogg','.mov']):
        return 'video'
    return 'document'


@login_required
def upload_record_view(request, hospital_number):
    patient = get_object_or_404(Patient, hospital_number=hospital_number)
    appointments = Appointment.objects.filter(patient=patient).order_by('-appointment_date')[:10]

    if request.method == 'POST':
        title       = request.POST.get('title', '').strip()
        record_type = request.POST.get('record_type', 'consultation')
        body        = request.POST.get('body', '').strip()
        visible     = 'is_visible_to_patient' in request.POST
        file        = request.FILES.get('attached_file')
        appt_id     = request.POST.get('appointment_id')

        if not title:
            messages.error(request, "Title is required.")
            return redirect('records:upload', hospital_number=hospital_number)

        record = MedicalRecord(
            patient=patient,
            record_type=record_type,
            title=title,
            body=body,
            is_visible_to_patient=visible,
            uploaded_by=request.user,
        )
        if file:
            max_size = 50 * 1024 * 1024
            if file.size > max_size:
                messages.error(request, "File too large. Maximum 50MB.")
                return redirect('records:upload', hospital_number=hospital_number)
            record.attached_file = file
        if appt_id:
            record.appointment_id = appt_id

        record.save()
        log_action(request.user, 'CREATE', request,
                   f"Uploaded record '{title}' for {hospital_number}")
        messages.success(request, f"Record '{title}' uploaded successfully.")
        return redirect('patient_detail:detail', hospital_number=hospital_number)

    return render(request, 'records/upload_record.html', {
        'page_title':   'Upload Record',
        'patient':      patient,
        'appointments': appointments,
        'record_types': MedicalRecord.RECORD_TYPE_CHOICES,
    })


@login_required
def record_detail_view(request, pk):
    record = get_object_or_404(MedicalRecord, pk=pk, is_deleted=False)

    if request.user.is_patient_user:
        if not hasattr(request.user, 'patient_profile') or \
           request.user.patient_profile != record.patient or \
           not record.is_visible_to_patient:
            messages.error(request, "Access denied.")
            return redirect('patients:dashboard')

    shares   = RecordShare.objects.filter(record=record).order_by('-shared_at')
    versions = RecordVersion.objects.filter(record=record)
    log_action(request.user, 'VIEW', request, f"Viewed record #{pk}: {record.title}")

    return render(request, 'records/record_detail.html', {
        'page_title': record.title,
        'record':     record,
        'shares':     shares,
        'versions':   versions,
    })


@login_required
def edit_record_view(request, pk):
    """Edit a record — saves a version snapshot before updating."""
    record = get_object_or_404(MedicalRecord, pk=pk, is_deleted=False)

    if not (request.user.is_admin_staff or request.user.is_doctor or
            request.user == record.uploaded_by):
        messages.error(request, "You don't have permission to edit this record.")
        return redirect('records:detail', pk=pk)

    if request.method == 'POST':
        change_note = request.POST.get('change_note', '').strip()

        # Save current state as a version snapshot BEFORE making changes
        RecordVersion.objects.create(
            record=record,
            version_num=record.version_number,
            title=record.title,
            body=record.body,
            record_type=record.record_type,
            is_visible_to_patient=record.is_visible_to_patient,
            edited_by=request.user,
            change_note=change_note or "Edited",
        )

        # Apply changes
        record.title       = request.POST.get('title', record.title).strip()
        record.body        = request.POST.get('body', record.body).strip()
        record.record_type = request.POST.get('record_type', record.record_type)
        record.is_visible_to_patient = 'is_visible_to_patient' in request.POST
        record.version_number += 1

        if 'attached_file' in request.FILES:
            record.attached_file = request.FILES['attached_file']

        record.save()
        log_action(request.user, 'UPDATE', request,
                   f"Edited record #{pk} (now v{record.version_number}): {change_note}")
        messages.success(request, f"Record updated. Version {record.version_number} saved.")
        return redirect('records:detail', pk=pk)

    return render(request, 'records/edit_record.html', {
        'page_title':   f"Edit: {record.title}",
        'record':       record,
        'record_types': MedicalRecord.RECORD_TYPE_CHOICES,
    })


@login_required
def version_history_view(request, pk):
    """Show all historical versions of a record."""
    record   = get_object_or_404(MedicalRecord, pk=pk, is_deleted=False)
    versions = RecordVersion.objects.filter(record=record)

    return render(request, 'records/version_history.html', {
        'page_title': f"History — {record.title}",
        'record':     record,
        'versions':   versions,
    })


@login_required
def restore_version_view(request, pk, version_num):
    """Restore a record to a specific previous version."""
    record  = get_object_or_404(MedicalRecord, pk=pk, is_deleted=False)
    version = get_object_or_404(RecordVersion, record=record, version_num=version_num)

    if not (request.user.is_admin_staff or request.user.is_doctor):
        messages.error(request, "Only doctors and admins can restore versions.")
        return redirect('records:history', pk=pk)

    if request.method == 'POST':
        # Save current state first
        RecordVersion.objects.create(
            record=record,
            version_num=record.version_number,
            title=record.title,
            body=record.body,
            record_type=record.record_type,
            is_visible_to_patient=record.is_visible_to_patient,
            edited_by=request.user,
            change_note=f"Restored to version {version_num}",
        )
        # Apply the old version
        record.title                  = version.title
        record.body                   = version.body
        record.record_type            = version.record_type
        record.is_visible_to_patient  = version.is_visible_to_patient
        record.version_number        += 1
        record.save()

        log_action(request.user, 'UPDATE', request,
                   f"Restored record #{pk} to v{version_num}")
        messages.success(request, f"Record restored to version {version_num}.")
        return redirect('records:detail', pk=pk)

    return render(request, 'records/restore_confirm.html', {
        'record':  record,
        'version': version,
    })


@login_required
def share_record_view(request, pk):
    """Create a secure share link for an external hospital."""
    record = get_object_or_404(MedicalRecord, pk=pk, is_deleted=False)

    if not (request.user.is_admin_staff or request.user.is_doctor):
        messages.error(request, "Only doctors and admins can share records.")
        return redirect('records:detail', pk=pk)

    if request.method == 'POST':
        from django.core.mail import send_mail
        from django.conf import settings

        recipient_name  = request.POST.get('recipient_name', '').strip()
        recipient_email = request.POST.get('recipient_email', '').strip()
        purpose         = request.POST.get('purpose', '').strip()
        hours           = int(request.POST.get('expires_hours', 48))

        if not recipient_name:
            messages.error(request, "Recipient name is required.")
            return redirect('records:share', pk=pk)

        share = RecordShare.objects.create(
            record=record,
            patient=record.patient,
            recipient_name=recipient_name,
            recipient_email=recipient_email,
            purpose=purpose,
            shared_by=request.user,
            expires_at=timezone.now() + timedelta(hours=hours),
        )

        share_url = request.build_absolute_uri(f'/records/shared/{share.token}/')

        # Send email if address provided
        if recipient_email:
            try:
                send_mail(
                    subject=f"Medical Record Shared — {settings.HOSPITAL_NAME}",
                    message=(
                        f"Dear {recipient_name},\n\n"
                        f"A medical record has been shared with you by "
                        f"Dr. {request.user.get_full_name()} from {settings.HOSPITAL_NAME}.\n\n"
                        f"Patient: {record.patient.full_name}\n"
                        f"Record: {record.title}\n"
                        f"Purpose: {purpose or 'Referral'}\n\n"
                        f"Access the record here (expires in {hours} hours):\n{share_url}\n\n"
                        f"This link will expire on {share.expires_at.strftime('%B %d, %Y at %H:%M')}.\n"
                        f"Do not share this link with anyone else.\n\n"
                        f"— {settings.HOSPITAL_NAME}"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient_email],
                    fail_silently=True,
                )
                messages.success(request,
                    f"Record shared. Link sent to {recipient_email}. Expires in {hours} hours.")
            except Exception:
                messages.success(request,
                    f"Share link created (email failed to send). Copy the link manually.")
        else:
            messages.success(request, f"Share link created. Expires in {hours} hours.")

        log_action(request.user, 'APPROVE', request,
                   f"Shared record #{pk} with {recipient_name} ({recipient_email})")
        return redirect('records:detail', pk=pk)

    return render(request, 'records/share_record.html', {
        'page_title': f"Share Record — {record.title}",
        'record':     record,
    })


def shared_record_view(request, token):
    """Public view — no login required. Validates token and shows record."""
    share = get_object_or_404(RecordShare, token=token)

    if share.is_revoked:
        return render(request, 'records/share_expired.html',
                      {'reason': 'This link has been revoked.'})
    if share.is_expired:
        return render(request, 'records/share_expired.html',
                      {'reason': 'This link has expired.'})

    # Log access
    share.access_count += 1
    share.accessed_at   = timezone.now()
    share.save()

    return render(request, 'records/shared_record_view.html', {
        'share':  share,
        'record': share.record,
    })


@login_required
def revoke_share_view(request, share_pk):
    share = get_object_or_404(RecordShare, pk=share_pk)
    if not (request.user.is_admin_staff or request.user == share.shared_by):
        messages.error(request, "Permission denied.")
        return redirect('records:detail', pk=share.record_id)
    share.is_revoked = True
    share.save()
    log_action(request.user, 'REVOKE', request, f"Revoked share #{share_pk}")
    messages.success(request, "Share link revoked.")
    return redirect('records:detail', pk=share.record_id)


@login_required
def delete_record_view(request, pk):
    record = get_object_or_404(MedicalRecord, pk=pk)
    if request.method == 'POST':
        record.soft_delete(request.user)
        log_action(request.user, 'DELETE', request, f"Archived record #{pk}: {record.title}")
        messages.success(request, "Record archived.")
        return redirect('patient_detail:detail', hospital_number=record.patient.hospital_number)
    return redirect('records:detail', pk=pk)


@login_required
def records_list_view(request):
    record_type_filter = request.GET.get('record_type', '')
    records = MedicalRecord.objects.filter(is_deleted=False).select_related('patient','uploaded_by')
    if record_type_filter:
        records = records.filter(record_type=record_type_filter)
    return render(request, 'records/records_list.html', {
        'page_title':  'Medical Records',
        'records':     records[:100],
        'record_types': MedicalRecord.RECORD_TYPE_CHOICES,
        'type_filter': record_type_filter,
    })


# ─────────────────────────────────────────────────────────────────────
# OCR — Extract text from uploaded scanned PDF or image
# ─────────────────────────────────────────────────────────────────────
@login_required
def ocr_extract_view(request, pk):
    """
    Run OCR on a record's attached file and populate the body field.
    Supports: scanned PDFs and images (JPG/PNG/GIF/WEBP).
    Uses Tesseract (free, local, no API limits).
    """
    record = get_object_or_404(MedicalRecord, pk=pk, is_deleted=False)

    if not record.attached_file:
        messages.error(request, "No file attached to this record.")
        return redirect('records:detail', pk=pk)

    if not (request.user.is_admin_staff or request.user.is_doctor or
            request.user.is_nurse or request.user == record.uploaded_by):
        messages.error(request, "Permission denied.")
        return redirect('records:detail', pk=pk)

    try:
        extracted = _run_ocr(record)
        if extracted.strip():
            # Save a version snapshot before overwriting
            RecordVersion.objects.create(
                record=record,
                version_num=record.version_number,
                title=record.title,
                body=record.body,
                record_type=record.record_type,
                is_visible_to_patient=record.is_visible_to_patient,
                edited_by=request.user,
                change_note="OCR text extraction",
            )
            record.body = extracted.strip()
            record.version_number += 1
            record.save()
            log_action(request.user, 'UPDATE', request,
                       f"OCR extracted {len(extracted)} chars from record #{pk}")
            messages.success(request,
                f"Text extracted successfully ({len(extracted)} characters). "
                f"Review and edit as needed.")
        else:
            messages.warning(request,
                "OCR ran but found no readable text. "
                "The document may be a non-text image or low quality scan.")
    except ImportError:
        messages.error(request,
            "OCR requires pytesseract and Tesseract to be installed. "
            "Run: pip install pytesseract Pillow pdf2image "
            "and install Tesseract from https://tesseract-ocr.github.io/")
    except Exception as e:
        messages.error(request, f"OCR failed: {str(e)}")

    return redirect('records:detail', pk=pk)


def _run_ocr(record):
    """
    Extract text from a file using Tesseract OCR.
    Handles both images and PDFs.
    """
    import pytesseract
    from PIL import Image
    import os

    file_path = record.attached_file.path
    file_type = record.file_type

    if file_type == 'image':
        img  = Image.open(file_path)
        text = pytesseract.image_to_string(img)
        return text

    elif file_type == 'pdf':
        # Convert PDF pages to images then OCR each page
        from pdf2image import convert_from_path
        pages = convert_from_path(file_path, dpi=200)
        text_parts = []
        for i, page in enumerate(pages):
            page_text = pytesseract.image_to_string(page)
            if page_text.strip():
                text_parts.append(f"--- Page {i+1} ---\n{page_text}")
        return '\n\n'.join(text_parts)

    else:
        raise ValueError(f"OCR is only supported for images and PDFs, not '{file_type}'.")
