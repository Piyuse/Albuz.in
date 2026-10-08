"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from django.contrib import admin
from django.urls import path
from django.urls import include, path
from django.conf import settings
from django.http import FileResponse, HttpResponse

def frontend(request):
    built = settings.BASE_DIR / 'frontend' / 'dist' / 'index.html'
    if not built.exists():
        return HttpResponse('Build the frontend with npm run build, or open the Vite development server on port 5173.', status=503)
    response = FileResponse(built.open('rb'), content_type='text/html; charset=utf-8')
    response['Cache-Control'] = 'no-cache'
    return response

urlpatterns = [
    path('', frontend, name='frontend'),
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/albums/', include('albums.urls')),
    path('api/integrations/', include('integrations.urls')),
]
