from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('inscription/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('theme/', views.update_theme, name='update_theme'),
    path('parametres/', views.settings_view, name='settings'),
]
