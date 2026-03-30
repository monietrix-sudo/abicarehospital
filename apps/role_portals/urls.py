from django.urls import path
from . import views
app_name = 'role_portals'
urlpatterns = [
    # Login pages
    path('doctor-portal/login/',    views.doctor_login_view,    name='doctor_login'),
    path('nurse-portal/login/',     views.nurse_login_view,     name='nurse_login'),
    path('lab-portal/login/',       views.lab_login_view,       name='lab_login'),
    path('reception-portal/login/', views.reception_login_view, name='reception_login'),
    # Dashboards
    path('doctor-portal/',          views.doctor_portal_view,    name='doctor_portal'),
    path('nurse-portal/',           views.nurse_portal_view,     name='nurse_portal'),
    path('lab-portal/',             views.lab_portal_view,       name='lab_portal'),
    path('reception-portal/',       views.reception_portal_view, name='reception_portal'),
]