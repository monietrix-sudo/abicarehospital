from django.urls import path
from . import views

app_name = 'families'

urlpatterns = [
    path('',
         views.family_list_view,
         name='list'),

    path('create/',
         views.create_family_view,
         name='create'),

    path('<int:pk>/',
         views.family_detail_view,
         name='detail'),

    path('<int:family_pk>/add-member/',
         views.add_member_view,
         name='add_member'),

    path('member/<int:member_pk>/remove/',
         views.remove_member_view,
         name='remove_member'),

    # AJAX endpoints
    path('api/search/',
         views.family_search_api,
         name='search_api'),

    path('convert/<str:hospital_number>/',
         views.convert_to_family_view,
         name='convert_to_family'),

    path('api/patient-search/',
         views.patient_search_for_family_api,
         name='patient_search_api'),
]