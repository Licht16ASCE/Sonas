from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', include('core.urls')),
    path('accounts/', include('accounts.urls')),
    path('sonas/agents/', include('accounts.urls_team')),
    path('client/', include('clients.urls_client')),
    path('client/biens/', include('biens.urls_client')),
    path('client/contrats/', include('contrats.urls_client')),
    path('client/sinistres/', include('sinistres.urls_client')),
    path('client/documents/', include('documents.urls_client')),
    path('client/notifications/', include('notifications.urls_client')),
    path('sonas/', include('core.urls_internal')),
    path('sonas/clients/', include('clients.urls_internal')),
    path('sonas/biens/', include('biens.urls')),
    path('sonas/contrats/', include('contrats.urls')),
    path('sonas/sinistres/', include('sinistres.urls')),
    path('sonas/documents/', include('documents.urls')),
    path('sonas/notifications/', include('notifications.urls')),
]

# Admin sécurisé — URL non exposée publiquement
urlpatterns += [
    path(settings.ADMIN_URL, admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
