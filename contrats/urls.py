from django.urls import path

from . import views

app_name = 'contrats'

urlpatterns = [
    path('', views.contrat_list, name='list'),
    path('nouveau/', views.contrat_create, name='create'),
    path('<int:pk>/', views.contrat_detail, name='detail'),
    path('<int:pk>/activer/', views.contrat_activate, name='activate'),
]
