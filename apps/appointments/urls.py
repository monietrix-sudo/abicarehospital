"""AbiCare - Appointments URLs."""
from django.urls import path
from . import views
app_name = 'appointments'
urlpatterns = [
    path('', views.appointment_list_view, name='list'),
    path('book/', views.book_appointment_view, name='book'),
    path('<int:pk>/', views.appointment_detail_view, name='detail'),
    path('<int:pk>/status/', views.update_appointment_status_view, name='update_status'),
    path('<int:pk>/approve/', views.approve_teleconsult_view, name='approve_teleconsult'),
    path('<int:pk>/join/', views.join_teleconsult_view, name='join_teleconsult'),
]
