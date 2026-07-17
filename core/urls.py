from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.landing, name='landing'),
    path('api/geo/adresses/', views.geo_adresse_search, name='geo_adresse_search'),
    path('api/geo/verify/', views.geo_adresse_verify, name='geo_adresse_verify'),
]
