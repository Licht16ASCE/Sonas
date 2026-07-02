from django.urls import path

from . import views

app_name = 'biens'

urlpatterns = [
    path('', views.bien_list, name='list'),
    path('nouveau/', views.bien_create, name='create'),
    path('<int:pk>/', views.bien_detail, name='detail'),
    path('<int:pk>/valider/', views.bien_validate, name='validate'),
]
