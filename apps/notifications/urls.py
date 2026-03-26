from django.urls import path
from . import views
app_name = 'notifications'
urlpatterns = [
    path('',                views.notification_list_view,  name='list'),
    path('unread/',         views.unread_count_api,        name='unread_count'),
    path('<int:pk>/read/',  views.mark_read_view,          name='mark_read'),
    path('mark-all-read/', views.mark_all_read_view,       name='mark_all_read'),
    path('preferences/',   views.preferences_view,         name='preferences'),
]
