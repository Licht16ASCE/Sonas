from django.urls import path

from . import views

app_name = 'core_internal'

urlpatterns = [
    path('', views.dashboard_internal, name='dashboard'),
    path('systeme/', views.admin_system, name='system'),
    path('logs/', views.admin_logs, name='logs'),
]
