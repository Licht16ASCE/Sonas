from django.urls import path

from . import views

app_name = 'documents_client'

urlpatterns = [
    path('', views.document_list, name='list'),
    path('upload/', views.document_upload, name='upload'),
]
