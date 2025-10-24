from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'clientes', views.ClienteViewSet, basename='cliente')
router.register(r'poblaciones', views.PoblacionViewSet, basename='poblacion')
router.register(r'clientes-sucursales', views.ClienteSucursalViewSet, basename='cliente-sucursal')

urlpatterns = [
    path('', include(router.urls)),
]
