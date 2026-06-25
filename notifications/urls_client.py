from django.urls import path

from . import views

app_name = 'notifications_client'

urlpatterns = [
    path('', views.notification_list, name='list'),
    path('<int:pk>/lire/', views.notification_mark_read, name='mark_read'),
    path('tout-lire/', views.notification_mark_all_read, name='mark_all_read'),
    path('actions/', views.pending_actions_list, name='pending_actions'),
]
