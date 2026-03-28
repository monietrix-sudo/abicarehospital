from django.urls import path
from . import views

app_name = 'imports'

urlpatterns = [
    path('patients/',
         views.import_patients_view,
         name='import_patients'),

    path('patients/export/',
         views.export_patients_view,
         name='export_patients'),

    path('patients/template/',
         views.download_template_view,
         name='download_template'),

    path('session/<int:pk>/',
         views.session_detail_view,
         name='session_detail'),
]