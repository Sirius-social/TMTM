"""xxx URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from django.conf.urls import url, include
from django.conf import settings
from ui.views import TransactionsView, IndexView
from wrapper.views import MaintenanceRouter, LedgersRouter, UploadView, ContentView


CONTENT_URL = settings.MEDIA_URL
if CONTENT_URL.startswith('/'):
    CONTENT_URL = CONTENT_URL[1:]


urlpatterns = [
    # Others
    path('transactions/', TransactionsView.as_view(), name='transactions'),
    path('', IndexView.as_view(), name='index'),
    # Uploads
    url(r'^upload', UploadView.as_view(), name='upload'),
    path(CONTENT_URL + '<uid>', ContentView.as_view(), name='content'),
    # Maintenance
    url(r'^', include(MaintenanceRouter.urls)),
    url(r'^', include(LedgersRouter.urls)),
]
