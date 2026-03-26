from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from .models import Notification, NotificationPreference


@login_required
def notification_list_view(request):
    notifs = Notification.objects.filter(user=request.user)
    notifs.filter(is_read=False).update(is_read=True)
    return render(request, 'notifications/notification_list.html', {
        'page_title': 'Notifications',
        'notifications': notifs[:50],
    })


@login_required
def unread_count_api(request):
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    notifs = list(
        Notification.objects.filter(user=request.user, is_read=False)
        .values('id','title','message','notif_type','link','created_at')[:8]
    )
    # Format datetimes for JSON
    for n in notifs:
        n['created_at'] = n['created_at'].strftime('%b %d, %H:%M')
    return JsonResponse({'count': count, 'notifications': notifs})


@login_required
def mark_read_view(request, pk):
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.is_read = True
    notif.save()
    if notif.link:
        return redirect(notif.link)
    return redirect('notifications:list')


@login_required
def mark_all_read_view(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect('notifications:list')


@login_required
def preferences_view(request):
    prefs, _ = NotificationPreference.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        prefs.email_enabled      = 'email_enabled' in request.POST
        prefs.inapp_enabled      = 'inapp_enabled' in request.POST
        prefs.whatsapp_enabled   = 'whatsapp_enabled' in request.POST
        prefs.whatsapp_number    = request.POST.get('whatsapp_number', '').strip()
        prefs.dose_overdue       = 'dose_overdue' in request.POST
        prefs.appointment_remind = 'appointment_remind' in request.POST
        prefs.result_released    = 'result_released' in request.POST
        prefs.save()
        messages.success(request, "Notification preferences saved.")
        return redirect('notifications:preferences')
    return render(request, 'notifications/preferences.html', {
        'page_title': 'Notification Settings',
        'prefs': prefs,
        'channels': [
            ('inapp_enabled',    'In-App Bell',     'fas fa-bell',       prefs.inapp_enabled),
            ('email_enabled',    'Email',            'fas fa-envelope',   prefs.email_enabled),
            ('whatsapp_enabled', 'WhatsApp',         'fab fa-whatsapp',   prefs.whatsapp_enabled),
        ],
    })
