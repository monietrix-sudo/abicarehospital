"""AbiCare - Patient Detail URL patterns (separate namespace)."""
from django.urls import path
from . import views

app_name = 'patient_detail'

urlpatterns = [
    path('', views.patient_list_view, name='list'),
    path('<str:hospital_number>/', views.patient_detail_view, name='detail'),
    path('<str:hospital_number>/edit/', views.edit_patient_view, name='edit'),
    path('<str:hospital_number>/deactivate/', views.deactivate_patient_view, name='deactivate'),
]
