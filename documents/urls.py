from django.urls import path

from . import views

app_name = 'documents'

urlpatterns = [
    path('', views.document_list, name='list'),
    path('upload/', views.document_upload, name='upload'),
    path('<int:pk>/apercu/', views.document_preview, name='preview'),
    path('<int:pk>/telecharger/', views.document_download, name='download'),
]
