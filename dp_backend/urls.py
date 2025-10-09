"""
URL configuration for dp_backend project.

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
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView
)

urlpatterns = [
    path("admin/", admin.site.urls),
    #Esquema de OpenAPI(JSON)
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    #Documentacion en swagger UI
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    #endpoints de API
    path("api/", include("users.urls")),
    path('api/clientes/', include('clientes.urls')),
    path('api/distribuidores/', include('distribuidores.urls')),
    path('api/vendedores/', include('vendedores.urls')),
    path('api/facturas/', include('facturas.urls')),
    path('api/pagos/', include('pagos.urls')),
    path('api/alertas/', include('alertas.urls')),
]
