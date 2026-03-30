from django.urls import path
from . import views
app_name = 'billing'
urlpatterns = [
    path('',                                     views.bill_list_view,             name='list'),
    path('create/<str:hospital_number>/',        views.create_bill_view,           name='create'),
    path('<int:pk>/',                            views.bill_detail_view,           name='bill_detail'),
    path('<int:pk>/send-to-nurse/',              views.send_to_nurse_view,         name='send_to_nurse'),
    path('<int:pk>/send-to-patient/',            views.send_to_patient_view,       name='send_to_patient'),
    path('<int:pk>/cash-payment/',               views.record_cash_payment_view,   name='cash_payment'),
    path('<int:pk>/paystack/init/',              views.paystack_initialize_view,   name='paystack_init'),
    path('paystack/callback/<int:pk>/',          views.paystack_callback_view,     name='paystack_callback'),
]