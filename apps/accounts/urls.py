from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/',                          views.login_view,                    name='login'),
    path('logout/',                         views.logout_view,                   name='logout'),
    path('profile/',                        views.profile_view,                  name='profile'),
    path('reset/',                          views.request_password_reset_view,   name='request_reset'),
    path('reset/<uuid:token>/',             views.do_password_reset_view,        name='do_reset'),
    path('admin/reset-requests/',           views.reset_requests_admin_view,     name='reset_requests'),
    path('admin/reset-requests/<int:pk>/',  views.review_reset_request_view,     name='review_reset'),
    path('patient-account/<str:hospital_number>/', views.create_patient_account_view, name='create_patient_account'),
]
