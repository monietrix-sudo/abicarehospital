from django.urls import path
from . import views
app_name = 'teleconsult'
urlpatterns = [path('', views.consult_links_view, name='links')]
