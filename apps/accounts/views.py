"""
AbiCare - Accounts Views
=========================
Includes:
- Login / Logout
- Profile update
- Password reset with admin approval workflow
- Patient portal account creation (by staff)
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.utils import timezone
from datetime import timedelta

from .models import User, PasswordResetRequest
from apps.audit_logs.utils import log_action


# ─────────────────────────────────────────────────────────────────────
# LOGIN / LOGOUT
# ─────────────────────────────────────────────────────────────────────
@never_cache
@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('patients:dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_active:
                login(request, user)
                log_action(user, 'LOGIN', request, f"Logged in: {user.username}")
                messages.success(request, f"Welcome back, {user.first_name or user.username}!")
                return redirect(request.GET.get('next', '/dashboard/'))
            else:
                messages.error(request, "Your account is deactivated. Contact admin.")
                log_action(None, 'LOGIN_FAIL', request, f"Deactivated login attempt: {username}")
        else:
            messages.error(request, "Invalid username or password.")
            log_action(None, 'LOGIN_FAIL', request, f"Failed login: {username}")

    return render(request, 'accounts/login.html', {'page_title': 'Login'})


@login_required
def logout_view(request):
    log_action(request.user, 'LOGOUT', request, f"Logged out: {request.user.username}")
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('accounts:login')


# ─────────────────────────────────────────────────────────────────────
# PROFILE
# ─────────────────────────────────────────────────────────────────────
@login_required
def profile_view(request):
    user = request.user
    if request.method == 'POST':
        user.first_name   = request.POST.get('first_name',   user.first_name).strip()
        user.last_name    = request.POST.get('last_name',    user.last_name).strip()
        user.email        = request.POST.get('email',        user.email).strip()
        user.phone_number = request.POST.get('phone_number', user.phone_number).strip()
        if 'profile_picture' in request.FILES:
            user.profile_picture = request.FILES['profile_picture']
        user.save()
        log_action(user, 'UPDATE', request, "Updated profile")
        messages.success(request, "Profile updated.")
        return redirect('accounts:profile')

    return render(request, 'accounts/profile.html', {
        'page_title':   'My Profile',
        'profile_user': user,
    })


# ─────────────────────────────────────────────────────────────────────
# PASSWORD RESET — patient requests, admin approves, then link is sent
# ─────────────────────────────────────────────────────────────────────
def request_password_reset_view(request):
    """
    Step 1: Patient enters their username/email to request a reset.
    No email is sent yet — admin must approve first.
    """
    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()

        # Find user by username or email
        user = None
        try:
            user = User.objects.get(username=identifier, is_active=True)
        except User.DoesNotExist:
            try:
                user = User.objects.get(email=identifier, is_active=True)
            except User.DoesNotExist:
                pass

        if user:
            # Check for recent pending request (rate-limit: 1 per hour)
            recent = PasswordResetRequest.objects.filter(
                user=user,
                status='pending',
                requested_at__gte=timezone.now() - timedelta(hours=1)
            ).exists()
            if not recent:
                # Get client IP
                x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
                ip = x_forwarded.split(',')[0] if x_forwarded else request.META.get('REMOTE_ADDR')

                reset_req = PasswordResetRequest.objects.create(
                    user=user,
                    ip_address=ip,
                )

                # Notify all admins
                admins = User.objects.filter(role='admin', is_active=True, email__isnull=False)
                from apps.notifications.utils import send_notification
                for admin in admins:
                    send_notification(
                        user=admin,
                        notif_type='general',
                        title=f"Password Reset Request — {user.get_full_name() or user.username}",
                        message=(
                            f"{user.get_full_name() or user.username} has requested a password reset. "
                            f"Please review and approve or deny in Admin → Password Reset Requests."
                        ),
                        link='/accounts/admin/reset-requests/',
                    )

                log_action(None, 'VIEW', request,
                           f"Password reset requested for: {user.username} from IP {ip}")

        # Always show the same message (security: don't reveal if user exists)
        messages.success(request,
            "If an account was found, your request has been sent to the administrator for approval. "
            "You will receive an email once it is approved."
        )
        return redirect('accounts:login')

    return render(request, 'accounts/request_reset.html', {'page_title': 'Request Password Reset'})


@login_required
def reset_requests_admin_view(request):
    """Admin view — list all pending reset requests and approve/deny them."""
    if not request.user.is_admin_staff:
        messages.error(request, "Admins only.")
        return redirect('patients:dashboard')

    pending  = PasswordResetRequest.objects.filter(status='pending').select_related('user')
    history  = PasswordResetRequest.objects.exclude(status='pending').select_related('user', 'reviewed_by')[:30]

    return render(request, 'accounts/reset_requests.html', {
        'page_title': 'Password Reset Requests',
        'pending':    pending,
        'history':    history,
    })


@login_required
def review_reset_request_view(request, pk):
    """Admin approves or denies a password reset request."""
    if not request.user.is_admin_staff:
        messages.error(request, "Admins only.")
        return redirect('patients:dashboard')

    reset_req = get_object_or_404(PasswordResetRequest, pk=pk, status='pending')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve':
            reset_req.status      = 'approved'
            reset_req.reviewed_by = request.user
            reset_req.reviewed_at = timezone.now()
            reset_req.expires_at  = timezone.now() + timedelta(hours=2)
            reset_req.save()

            # Now send the reset email to the patient
            _send_reset_email(request, reset_req)

            log_action(request.user, 'APPROVE', request,
                       f"Approved password reset for {reset_req.user.username}")
            messages.success(request,
                f"Approved. Reset link emailed to {reset_req.user.email or reset_req.user.username}.")

        elif action == 'deny':
            reset_req.status      = 'denied'
            reset_req.reviewed_by = request.user
            reset_req.reviewed_at = timezone.now()
            reset_req.save()

            log_action(request.user, 'DELETE', request,
                       f"Denied password reset for {reset_req.user.username}")
            messages.info(request, f"Request denied for {reset_req.user.username}.")

        return redirect('accounts:reset_requests')

    return redirect('accounts:reset_requests')


def _send_reset_email(request, reset_req):
    """Send the actual password reset link email after admin approval."""
    from django.core.mail import send_mail
    from django.conf import settings

    reset_url = request.build_absolute_uri(
        f'/accounts/reset/{reset_req.token}/'
    )
    user = reset_req.user

    if not user.email:
        return  # No email on file

    try:
        send_mail(
            subject=f"[{settings.HOSPITAL_NAME}] Password Reset Approved",
            message=(
                f"Dear {user.get_full_name() or user.username},\n\n"
                f"Your password reset request has been approved by the administrator.\n\n"
                f"Click the link below to set a new password (expires in 2 hours):\n"
                f"{reset_url}\n\n"
                f"If you did not request this, please contact {settings.HOSPITAL_NAME} immediately.\n\n"
                f"— {settings.HOSPITAL_NAME}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception:
        pass


def do_password_reset_view(request, token):
    """Step 3: Patient clicks the link and sets a new password."""
    reset_req = get_object_or_404(PasswordResetRequest, token=token)

    if not reset_req.is_valid:
        messages.error(request, "This reset link has expired or already been used.")
        return redirect('accounts:login')

    if request.method == 'POST':
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        if not password1 or len(password1) < 8:
            messages.error(request, "Password must be at least 8 characters.")
            return render(request, 'accounts/do_reset.html', {'token': token})

        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return render(request, 'accounts/do_reset.html', {'token': token})

        user = reset_req.user
        user.set_password(password1)
        user.save()

        reset_req.status = 'used'
        reset_req.save()

        log_action(user, 'UPDATE', request, "Password reset successfully via approved link")
        messages.success(request, "Password updated successfully. You can now log in.")
        return redirect('accounts:login')

    return render(request, 'accounts/do_reset.html', {
        'page_title': 'Set New Password',
        'token': token,
        'user': reset_req.user,
    })


# ─────────────────────────────────────────────────────────────────────
# PATIENT PORTAL ACCOUNT CREATION (by staff)
# ─────────────────────────────────────────────────────────────────────
@login_required
def create_patient_account_view(request, hospital_number):
    """
    Any staff member can create a portal login for a patient.
    Accessible from the patient profile page.
    """
    from apps.patients.models import Patient
    patient = get_object_or_404(Patient, hospital_number=hospital_number)

    # Check patient doesn't already have an account
    if patient.user_account:
        messages.warning(request,
            f"{patient.full_name} already has a portal account: {patient.user_account.username}")
        return redirect('patient_detail:detail', hospital_number=hospital_number)

    if request.method == 'POST':
        username    = request.POST.get('username', '').strip()
        password1   = request.POST.get('password1', '')
        password2   = request.POST.get('password2', '')
        send_email  = 'send_email' in request.POST

        # Validate
        if not username:
            messages.error(request, "Username is required.")
        elif User.objects.filter(username=username).exists():
            messages.error(request, f"Username '{username}' is already taken.")
        elif len(password1) < 8:
            messages.error(request, "Password must be at least 8 characters.")
        elif password1 != password2:
            messages.error(request, "Passwords do not match.")
        else:
            # Create the portal user account
            portal_user = User.objects.create_user(
                username=username,
                password=password1,
                first_name=patient.first_name,
                last_name=patient.last_name,
                email=patient.email,
                role=User.PATIENT,
            )
            patient.user_account = portal_user
            patient.save()

            # Send welcome email if requested
            if send_email and patient.email:
                from django.core.mail import send_mail
                from django.conf import settings
                try:
                    send_mail(
                        subject=f"Welcome to {settings.HOSPITAL_NAME} Patient Portal",
                        message=(
                            f"Dear {patient.full_name},\n\n"
                            f"Your patient portal account has been created.\n\n"
                            f"Username: {username}\n"
                            f"Password: {password1}\n\n"
                            f"Login at: {request.build_absolute_uri('/accounts/login/')}\n\n"
                            f"Please change your password after first login.\n\n"
                            f"— {settings.HOSPITAL_NAME}"
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[patient.email],
                        fail_silently=True,
                    )
                except Exception:
                    pass

            log_action(request.user, 'CREATE', request,
                       f"Created portal account '{username}' for patient {hospital_number}")
            messages.success(request,
                f"Portal account created for {patient.full_name}. "
                f"Username: {username}"
                + (" — Welcome email sent." if send_email and patient.email else "")
            )
            return redirect('patient_detail:detail', hospital_number=hospital_number)

    return render(request, 'accounts/create_patient_account.html', {
        'page_title': f"Create Portal Account — {patient.full_name}",
        'patient':    patient,
        # Suggest username from name
        'suggested_username': f"{patient.first_name.lower()}.{patient.last_name.lower()}".replace(' ', ''),
    })
