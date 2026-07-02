from django.urls import path

from . import views

app_name = 'clients_client'

urlpatterns = [
    path('', views.client_dashboard, name='dashboard'),
    path('profil/', views.client_profile, name='profile'),
    path('activites/', views.client_activites, name='activites'),
]
