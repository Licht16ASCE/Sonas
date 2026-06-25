from django.urls import path

from . import views_team

app_name = 'accounts_team'

urlpatterns = [
    path('', views_team.agent_list, name='list'),
    path('nouveau/', views_team.agent_create, name='create'),
    path('<int:pk>/toggle/', views_team.agent_toggle_active, name='toggle_active'),
]
