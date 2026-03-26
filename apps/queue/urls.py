from django.urls import path
from . import views
app_name = 'queue'
urlpatterns = [
    path('',                    views.queue_view,           name='list'),
    path('add/',                views.add_to_queue_view,    name='add'),
    path('checkin/',            views.self_checkin_view,    name='self_checkin'),
    path('<int:pk>/call/',      views.call_patient_view,    name='call'),
    path('<int:pk>/status/',    views.update_status_view,   name='status'),
    path('display/',            views.display_board_view,   name='display'),
    path('api/status/',         views.queue_status_api,     name='api_status'),
]
