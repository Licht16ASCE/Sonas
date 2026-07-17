from django.urls import path

from . import views

app_name = 'contrats_client'

urlpatterns = [
    path('', views.contrat_list_client, name='list'),
    path('nouveau/', views.contrat_create_client, name='create'),
    path('<int:pk>/', views.contrat_detail_client, name='detail'),
    path('<int:pk>/consolidation/', views.contrat_consolidation_client, name='consolidation'),
    path('<int:pk>/preuve/', views.contrat_upload_preuve, name='upload_preuve'),
]
