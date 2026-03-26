"""
AbiCare - Audit + Admin Re-Auth Middleware
==========================================
1. X-Robots-Tag: noindex on ALL responses (blocks crawlers).
2. Logs every page access to AuditLog for authenticated users.
3. AdminReAuthMiddleware: forces password re-entry before /admin/ access,
   even if the user is already logged in. Session expires after 30 minutes.
"""

from django.shortcuts import redirect, render
from django.utils import timezone
from django.contrib.auth import authenticate

from .utils import log_action

# How long (seconds) an admin session stays valid without re-entry
ADMIN_SESSION_SECONDS = 1800   # 30 minutes
ADMIN_SESSION_KEY     = '_admin_verified_at'


class AdminReAuthMiddleware:
    """
    Intercepts any request to /admin/ and checks whether the user
    re-authenticated within the last 30 minutes.

    If not → show the password confirmation screen.
    If yes → let them through normally.

    This protects against:
    - Stolen phones / unattended screens where someone is already logged in
    - Session hijacking (attacker gets the EHR session but still can't reach admin)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/') and not request.path.startswith('/admin/login'):

            # Must be logged in AND be staff to use admin at all
            if not request.user.is_authenticated or not request.user.is_staff:
                return redirect(f'/admin/login/?next={request.path}')

            now         = timezone.now().timestamp()
            verified_at = request.session.get(ADMIN_SESSION_KEY, 0)

            # Check if re-auth window has expired
            if now - verified_at > ADMIN_SESSION_SECONDS:
                # POST → user just submitted the confirmation form
                if request.method == 'POST' and '_reauth_password' in request.POST:
                    password = request.POST.get('_reauth_password', '')
                    user = authenticate(request,
                                        username=request.user.username,
                                        password=password)
                    if user is not None:
                        request.session[ADMIN_SESSION_KEY] = timezone.now().timestamp()
                        log_action(user, 'LOGIN', request, "Admin re-authentication successful")
                        return redirect(request.path)
                    else:
                        log_action(request.user, 'LOGIN', request,
                                   "Admin re-authentication FAILED — wrong password")
                        return render(request, 'admin/admin_reauth.html', {
                            'error': 'Incorrect password. Please try again.',
                            'next': request.path,
                        })

                # GET → show the re-auth form
                return render(request, 'admin/admin_reauth.html', {
                    'next': request.path,
                })

        return self.get_response(request)


class AuditMiddleware:
    """
    Sits in the middleware stack and fires on every response.
    X-Robots-Tag ensures even if robots.txt is missed, bots get blocked.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Block ALL crawlers at HTTP header level
        response['X-Robots-Tag'] = 'noindex, nofollow, noarchive, nosnippet'

        # Log page views for authenticated users
        skip_prefixes = ('/static/', '/media/', '/admin/jsi18n/', '/favicon')
        path = request.path

        if (
            request.user.is_authenticated
            and not any(path.startswith(p) for p in skip_prefixes)
            and request.method == 'GET'
            and response.status_code == 200
        ):
            log_action(request.user, 'VIEW', request, f"Page accessed: {path}")

        return response
