from django.urls import path

from . import views

app_name = 'sinistres_client'

urlpatterns = [
    path('', views.sinistre_list_client, name='list'),
    path('nouveau/', views.sinistre_create_client, name='create'),
    path('<int:pk>/', views.sinistre_detail_client, name='detail'),
    path('<int:pk>/preuve-retrait/', views.sinistre_upload_preuve_retrait, name='upload_preuve_retrait'),
    path('rapports/<int:pk>/', views.rapport_indemnisation_detail, name='rapport'),
]
