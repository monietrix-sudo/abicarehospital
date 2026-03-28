from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Login / Logout
    path('login/',                           views.login_view,                        name='login'),
    path('logout/',                          views.logout_view,                       name='logout'),

    # Forced password change (first login)
    path('change-password/',                 views.force_change_password_view,        name='force_change_password'),

    # Profile
    path('profile/',                         views.profile_view,                      name='profile'),

    # Patient portal accounts
    path('patient-account/<str:hospital_number>/',
                                             views.create_patient_account_view,       name='create_patient_account'),
    path('patient-account/<str:hospital_number>/print/',
                                             views.print_patient_credentials_view,    name='print_patient_credentials'),
    path('patient-account/<str:hospital_number>/reset-password/',
                                             views.admin_reset_patient_password_view, name='reset_patient_password'),

    # Staff accounts
    path('staff/',                           views.staff_list_view,                   name='staff_list'),
    path('staff/create/',                    views.create_staff_account_view,         name='create_staff_account'),
    path('staff/<int:pk>/reset-password/',   views.admin_reset_staff_password_view,   name='reset_staff_password'),

    # Self-service password reset (admin approval required)
    path('reset/',                           views.request_password_reset_view,       name='request_reset'),
    path('reset/<uuid:token>/',              views.do_password_reset_view,            name='do_reset'),
    path('admin/reset-requests/',            views.reset_requests_admin_view,         name='reset_requests'),
    path('admin/reset-requests/<int:pk>/',   views.review_reset_request_view,         name='review_reset'),
]