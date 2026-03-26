from django.urls import path
from . import views

app_name = 'lab_results'

urlpatterns = [
    path('',                                      views.lab_result_list_view,     name='list'),
    path('templates/',                            views.manage_templates_view,    name='templates'),
    path('templates/upload-pdf/',                 views.upload_pdf_template_view, name='upload_pdf_template'),
    path('<int:pk>/',                             views.lab_result_detail_view,   name='detail'),
    path('<int:pk>/fill/',                        views.fill_lab_result_view,     name='fill'),
    path('<int:pk>/annotate/',                    views.annotate_pdf_result_view, name='annotate'),
    path('<int:pk>/save-annotations/',            views.save_annotations_view,    name='save_annotations'),
    path('<int:pk>/release/',                     views.release_lab_result_view,  name='release'),
    path('order/<str:patient_hospital_number>/',  views.order_lab_test_view,      name='order'),
]
