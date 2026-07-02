from django.urls import path

from . import views

app_name = 'sinistres'

urlpatterns = [
    path('', views.sinistre_list, name='list'),
    path('nouveau/', views.sinistre_create, name='create'),
    path('<int:pk>/', views.sinistre_detail, name='detail'),
    path('<int:pk>/statut/', views.sinistre_update_status, name='update_status'),
    path('<int:pk>/traiter/', views.sinistre_traiter, name='traiter'),
    path('<int:pk>/valider/', views.sinistre_validate, name='validate'),
    path('rapports/<int:pk>/', views.rapport_indemnisation_detail, name='rapport'),
]
