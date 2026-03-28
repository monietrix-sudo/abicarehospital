from django.urls import path
from . import views

app_name = 'portal'

urlpatterns = [
    path('',                          views.portal_dashboard_view,         name='dashboard'),
    path('profile/',                  views.portal_profile_view,           name='profile'),
    path('lab-results/',              views.portal_lab_results_view,       name='lab_results'),
    path('lab-results/<int:pk>/',     views.portal_lab_result_detail_view, name='lab_result_detail'),
    path('medications/',              views.portal_medications_view,       name='medications'),
    path('medications/dose/<int:dose_pk>/tick/',
                                      views.portal_tick_dose_view,         name='tick_dose'),
    path('appointments/',             views.portal_appointments_view,      name='appointments'),
    path('records/',                  views.portal_records_view,           name='records'),
    path('records/<int:pk>/',         views.portal_record_detail_view,     name='record_detail'),
]