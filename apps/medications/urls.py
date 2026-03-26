from django.urls import path
from . import views
app_name = 'medications'
urlpatterns = [
    path('', views.patient_medications_view, name='list'),
    path('prescribe/<str:patient_hospital_number>/', views.prescribe_medication_view, name='prescribe'),
    path('schedule/<int:schedule_id>/', views.medication_timetable_view, name='timetable'),
    path('dose/<int:dose_id>/tick/', views.tick_dose_view, name='tick_dose'),
]
