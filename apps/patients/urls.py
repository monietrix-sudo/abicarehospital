"""AbiCare - Patients/Dashboard URLs."""
from django.urls import path
from . import views

app_name = 'patients'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('search/', views.quick_search_api, name='quick_search'),
    path('add/', views.add_patient_view, name='add_patient'),
]
