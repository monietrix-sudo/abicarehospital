"""
AbiCare - Billing Views
========================
Doctor creates bill → Nurse receives → Patient pays → Nurse confirms → Doctor notified
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
import json, uuid

from .models import Bill, BillItem, Payment, PaystackTransaction
from apps.audit_logs.utils import log_action
from apps.notifications.utils import send_notification


def _require_roles(*roles):
    """Helper: check role inside a view."""
    def decorator(view_func):
        from functools import wraps
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            if request.user.is_superuser or request.user.role in roles:
                return view_func(request, *args, **kwargs)
            messages.error(request, "You do not have permission to access billing.")
            return redirect('patients:dashboard')
        return wrapper
    return decorator


# ─────────────────────────────────────────────────────────────────────
# DOCTOR: Create and manage bills
# ─────────────────────────────────────────────────────────────────────

@login_required
@_require_roles('doctor', 'admin')
def create_bill_view(request, hospital_number):
    from apps.patients.models import Patient
    from apps.clinical_records.models import PatientEncounter
    from apps.accounts.models import User

    patient   = get_object_or_404(Patient, hospital_number=hospital_number)
    encounters = PatientEncounter.objects.filter(patient=patient).order_by('-encounter_date')[:10]
    nurses     = User.objects.filter(role='nurse', is_active=True)

    if request.method == 'POST':
        encounter_id = request.POST.get('encounter_id')
        nurse_id     = request.POST.get('nurse_id')
        notes        = request.POST.get('notes', '').strip()
        patient_msg  = request.POST.get('patient_message', '').strip()

        bill = Bill.objects.create(
            patient=patient,
            encounter_id=encounter_id if encounter_id else None,
            created_by=request.user,
            assigned_nurse_id=nurse_id if nurse_id else None,
            notes=notes,
            patient_message=patient_msg,
            status='draft',
        )

        # Process line items
        descriptions = request.POST.getlist('item_description')
        item_types   = request.POST.getlist('item_type')
        quantities   = request.POST.getlist('item_quantity')
        unit_prices  = request.POST.getlist('item_unit_price')
        discounts    = request.POST.getlist('item_discount')

        total = 0
        for i, desc in enumerate(descriptions):
            if not desc.strip():
                continue
            qty       = int(quantities[i]) if i < len(quantities) else 1
            price     = float(unit_prices[i]) if i < len(unit_prices) else 0
            discount  = float(discounts[i]) if i < len(discounts) else 0
            item_type = item_types[i] if i < len(item_types) else 'other'

            item = BillItem.objects.create(
                bill=bill,
                item_type=item_type,
                description=desc.strip(),
                quantity=qty,
                unit_price=price,
                discount=discount,
            )
            total += item.subtotal

        bill.total_amount = total
        bill.save()

        log_action(request.user, 'CREATE', request,
                   f"Created bill #{bill.bill_number_short} for {hospital_number} — ₦{total}")
        messages.success(request,
            f"Bill created — ₦{total:,.2f}. "
            f"Click 'Send to Nurse' when ready.")
        return redirect('billing:bill_detail', pk=bill.pk)

    return render(request, 'billing/create_bill.html', {
        'page_title':  f"Create Bill — {patient.full_name}",
        'patient':     patient,
        'encounters':  encounters,
        'nurses':      nurses,
        'item_types':  BillItem.ITEM_TYPE_CHOICES,
    })


@login_required
@_require_roles('doctor', 'admin')
def send_to_nurse_view(request, pk):
    bill = get_object_or_404(Bill, pk=pk)

    if request.method == 'POST':
        if not bill.assigned_nurse:
            messages.error(request, "Please assign a nurse before sending.")
            return redirect('billing:bill_detail', pk=pk)

        bill.status            = 'sent_to_nurse'
        bill.sent_to_nurse_at  = timezone.now()
        bill.save()

        # Notify the nurse
        send_notification(
            user=bill.assigned_nurse,
            notif_type='general',
            title=f"New Bill — {bill.patient.full_name}",
            message=(
                f"Dr. {request.user.get_full_name()} has sent a bill of "
                f"₦{bill.total_amount:,.2f} for {bill.patient.full_name}. "
                f"Please review and forward to the patient."
            ),
            link=f'/billing/{bill.pk}/',
            patient_id=bill.patient_id,
        )

        log_action(request.user, 'UPDATE', request,
                   f"Sent bill #{bill.bill_number_short} to nurse {bill.assigned_nurse.username}")
        messages.success(request,
            f"Bill sent to {bill.assigned_nurse.get_full_name() or bill.assigned_nurse.username}.")

    return redirect('billing:bill_detail', pk=pk)


@login_required
def bill_detail_view(request, pk):
    bill = get_object_or_404(Bill, pk=pk)
    items    = bill.items.all()
    payments = bill.payments.all()

    # Access control
    user = request.user
    can_view = (
        user.is_admin_staff or user.is_superuser or
        user == bill.created_by or
        user == bill.assigned_nurse or
        (user.is_patient_user and
         hasattr(user, 'patient_profile') and
         user.patient_profile == bill.patient and
         bill.status in ['sent_to_patient', 'partially_paid'])
    )
    if not can_view:
        messages.error(request, "Access denied.")
        return redirect('patients:dashboard')

    paystack_key = getattr(settings, 'PAYSTACK_PUBLIC_KEY', '')

    return render(request, 'billing/bill_detail.html', {
        'page_title':   f"Bill — {bill.patient.full_name}",
        'bill':         bill,
        'items':        items,
        'payments':     payments,
        'paystack_key': paystack_key,
    })


# ─────────────────────────────────────────────────────────────────────
# NURSE: Forward to patient
# ─────────────────────────────────────────────────────────────────────

@login_required
@_require_roles('nurse', 'admin')
def send_to_patient_view(request, pk):
    bill = get_object_or_404(Bill, pk=pk)
    if request.method == 'POST':
        bill.status              = 'sent_to_patient'
        bill.sent_to_patient_at  = timezone.now()
        bill.save()

        if bill.patient.user_account:
            send_notification(
                user=bill.patient.user_account,
                notif_type='general',
                title=f"New Bill — ₦{bill.total_amount:,.2f}",
                message=(
                    bill.patient_message or
                    f"You have a new bill of ₦{bill.total_amount:,.2f}. "
                    f"Please log into your portal to view and pay."
                ),
                link=f'/portal/billing/{bill.pk}/',
            )

        log_action(request.user, 'UPDATE', request,
                   f"Forwarded bill #{bill.bill_number_short} to patient portal")
        messages.success(request, "Bill sent to patient portal.")
    return redirect('billing:bill_detail', pk=pk)


@login_required
@_require_roles('nurse', 'admin')
def record_cash_payment_view(request, pk):
    bill = get_object_or_404(Bill, pk=pk)
    if request.method == 'POST':
        amount = float(request.POST.get('amount', 0))
        notes  = request.POST.get('notes', '').strip()

        payment = Payment.objects.create(
            bill=bill,
            amount=amount,
            method='cash',
            recorded_by=request.user,
            notes=notes,
            is_verified=True,
            verified_by=request.user,
        )

        bill.amount_paid += amount
        if bill.is_fully_paid:
            bill.status   = 'paid'
            bill.paid_at  = timezone.now()
        else:
            bill.status   = 'partially_paid'
        bill.save()

        # Notify doctor
        if bill.created_by:
            send_notification(
                user=bill.created_by,
                notif_type='general',
                title=f"Payment Received — {bill.patient.full_name}",
                message=(
                    f"Cash payment of ₦{amount:,.2f} recorded for "
                    f"{bill.patient.full_name}. "
                    f"Balance: ₦{bill.balance:,.2f}. "
                    f"Status: {bill.get_status_display()}."
                ),
                link=f'/billing/{bill.pk}/',
                patient_id=bill.patient_id,
            )

        log_action(request.user, 'CREATE', request,
                   f"Recorded cash payment ₦{amount} for bill #{bill.bill_number_short}")
        messages.success(request,
            f"Cash payment of ₦{amount:,.2f} recorded. "
            f"Balance: ₦{bill.balance:,.2f}.")

    return redirect('billing:bill_detail', pk=pk)


# ─────────────────────────────────────────────────────────────────────
# PAYSTACK: Initialise and verify
# ─────────────────────────────────────────────────────────────────────

@login_required
def paystack_initialize_view(request, pk):
    bill    = get_object_or_404(Bill, pk=pk)
    patient = bill.patient

    if not patient.user_account or request.user != patient.user_account:
        messages.error(request, "Access denied.")
        return redirect('portal:dashboard')

    import requests as http_requests
    secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', '')
    if not secret_key:
        messages.error(request, "Paystack is not configured. Please pay by cash or bank transfer.")
        return redirect('portal:billing_detail', pk=pk)

    reference = f"ABI-{bill.bill_number_short}-{uuid.uuid4().hex[:8].upper()}"
    amount_kobo = int(bill.balance * 100)

    try:
        resp = http_requests.post(
            'https://api.paystack.co/transaction/initialize',
            headers={'Authorization': f'Bearer {secret_key}'},
            json={
                'email':     patient.email or patient.user_account.email,
                'amount':    amount_kobo,
                'reference': reference,
                'callback_url': request.build_absolute_uri(
                    f'/billing/paystack/callback/{pk}/'
                ),
                'metadata': {
                    'bill_pk':         pk,
                    'patient_name':    patient.full_name,
                    'hospital_number': patient.hospital_number,
                }
            }
        )
        data = resp.json()
        if data.get('status'):
            PaystackTransaction.objects.create(
                bill=bill,
                reference=reference,
                amount=bill.balance,
                status='pending',
            )
            return redirect(data['data']['authorization_url'])
        else:
            messages.error(request,
                f"Paystack error: {data.get('message','Unknown error')}")
    except Exception as e:
        messages.error(request, f"Payment failed: {str(e)}")

    return redirect('portal:billing_detail', pk=pk)


def paystack_callback_view(request, pk):
    """Paystack redirects here after payment attempt."""
    bill      = get_object_or_404(Bill, pk=pk)
    reference = request.GET.get('reference', '')

    if not reference:
        messages.error(request, "Invalid payment reference.")
        return redirect('portal:dashboard')

    # Verify with Paystack
    import requests as http_requests
    secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', '')
    try:
        resp = http_requests.get(
            f'https://api.paystack.co/transaction/verify/{reference}',
            headers={'Authorization': f'Bearer {secret_key}'},
        )
        data = resp.json()
        txn  = data.get('data', {})

        ps_txn = PaystackTransaction.objects.filter(
            reference=reference, bill=bill
        ).first()

        if txn.get('status') == 'success':
            amount_paid = txn['amount'] / 100
            if ps_txn:
                ps_txn.status  = 'success'
                ps_txn.paid_at = timezone.now()
                ps_txn.gateway_response = str(txn)
                ps_txn.save()

            Payment.objects.create(
                bill=bill,
                amount=amount_paid,
                method='paystack',
                reference=reference,
                is_verified=True,
            )
            bill.amount_paid += amount_paid
            if bill.is_fully_paid:
                bill.status  = 'paid'
                bill.paid_at = timezone.now()
            else:
                bill.status  = 'partially_paid'
            bill.paystack_reference = reference
            bill.paystack_verified  = True
            bill.save()

            # Notify nurse and doctor
            if bill.assigned_nurse:
                send_notification(
                    user=bill.assigned_nurse,
                    notif_type='general',
                    title=f"Online Payment — {bill.patient.full_name}",
                    message=(
                        f"Paystack payment of ₦{amount_paid:,.2f} received from "
                        f"{bill.patient.full_name}. "
                        f"Reference: {reference}. "
                        f"Balance: ₦{bill.balance:,.2f}."
                    ),
                    link=f'/billing/{bill.pk}/',
                )
            if bill.created_by:
                send_notification(
                    user=bill.created_by,
                    notif_type='general',
                    title=f"Paystack Payment — {bill.patient.full_name}",
                    message=(
                        f"₦{amount_paid:,.2f} paid online via Paystack. "
                        f"Balance: ₦{bill.balance:,.2f}."
                    ),
                    link=f'/billing/{bill.pk}/',
                )

            messages.success(request,
                f"Payment of ₦{amount_paid:,.2f} confirmed. Thank you!")
            log_action(request.user if request.user.is_authenticated else None,
                       'CREATE', request,
                       f"Paystack payment verified: {reference} for bill #{bill.bill_number_short}")
        else:
            messages.error(request,
                f"Payment was not successful. Status: {txn.get('status','unknown')}. "
                f"Please try again or pay by cash.")
    except Exception as e:
        messages.error(request, f"Payment verification failed: {str(e)}")

    if request.user.is_authenticated and request.user.is_patient_user:
        return redirect('portal:dashboard')
    return redirect('billing:bill_detail', pk=pk)


@login_required
def bill_list_view(request):
    user  = request.user
    bills = Bill.objects.all()

    if user.is_patient_user:
        if hasattr(user, 'patient_profile'):
            bills = bills.filter(
                patient=user.patient_profile,
                status__in=['sent_to_patient', 'partially_paid', 'paid']
            )
        else:
            bills = Bill.objects.none()
    elif user.role == 'nurse':
        bills = bills.filter(
            assigned_nurse=user,
            status__in=['sent_to_nurse', 'sent_to_patient', 'partially_paid', 'paid']
        )
    elif user.role == 'doctor':
        bills = bills.filter(created_by=user)
    # admin sees all

    return render(request, 'billing/bill_list.html', {
        'page_title': 'Bills & Payments',
        'bills':      bills.select_related('patient', 'created_by', 'assigned_nurse'),
    })

# Create your views here.
