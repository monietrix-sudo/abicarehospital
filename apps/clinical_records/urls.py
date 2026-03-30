from django.urls import path
from . import views
app_name = 'clinical_records'
urlpatterns = [
    path('patient/<str:hospital_number>/',        views.patient_records_view,     name='patient_records'),
    path('patient/<str:hospital_number>/add/',    views.add_encounter_view,       name='add_encounter'),
    path('encounter/<int:pk>/',                   views.encounter_detail_view,    name='encounter_detail'),
    path('encounter/<int:pk>/edit/',              views.edit_encounter_view,      name='edit_encounter'),
    path('encounter/<int:pk>/diagnosis/add/',     views.add_diagnosis_view,       name='add_diagnosis'),
    path('encounter/<int:pk>/operation/add/',     views.add_operation_view,       name='add_operation'),
    path('encounter/<int:pk>/approve-patient/',   views.approve_for_patient_view, name='approve_patient'),
    path('diagnosis/<int:pk>/delete/',            views.delete_diagnosis_view,    name='delete_diagnosis'),
]