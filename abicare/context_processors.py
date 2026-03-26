from django.conf import settings

def hospital_settings(request):
    return {
        'HOSPITAL_NAME':          settings.HOSPITAL_NAME,
        'HOSPITAL_TAGLINE':       settings.HOSPITAL_TAGLINE,
        'HOSPITAL_ADDRESS':       settings.HOSPITAL_ADDRESS,
        'HOSPITAL_PHONE':         settings.HOSPITAL_PHONE,
        'HOSPITAL_EMAIL':         settings.HOSPITAL_EMAIL,
        'HOSPITAL_PRIMARY_COLOR': settings.HOSPITAL_PRIMARY_COLOR,
        'HOSPITAL_ACCENT_COLOR':  settings.HOSPITAL_ACCENT_COLOR,
        'HOSPITAL_WEBSITE':       settings.HOSPITAL_WEBSITE,
    }
