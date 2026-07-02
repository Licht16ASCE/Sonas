from django.urls import path

from . import views

app_name = 'biens_client'

urlpatterns = [
    path('', views.bien_list_client, name='list'),
    path('nouveau/', views.bien_create_client, name='create'),
    path('<int:pk>/', views.bien_detail_client, name='detail'),
]
