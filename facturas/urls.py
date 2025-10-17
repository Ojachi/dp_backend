from django.urls import path

from . import views

urlpatterns = [
    # CRUD de facturas
    path('', views.FacturaListCreateView.as_view(), name='factura-list-create'),
    path('<int:pk>/', views.FacturaDetailView.as_view(), name='factura-detail'),

    # Endpoints especiales
    path('pendientes/', views.facturas_pendientes, name='facturas-pendientes'),
    path('vencidas/', views.facturas_vencidas, name='facturas-vencidas'),
    path('dashboard/', views.dashboard_facturas, name='dashboard-facturas'),

    # Flujo de importación
    path('importacion/validar/', views.validar_importacion_facturas, name='facturas-importacion-validar'),
    path('importacion/vista-previa/', views.vista_previa_importacion, name='facturas-importacion-vista-previa'),
    path('importacion/confirmar/', views.confirmar_importacion, name='facturas-importacion-confirmar'),
    path('importacion/<int:pk>/estado/', views.estado_importacion, name='facturas-importacion-estado'),
    path('importacion/historial/', views.historial_importaciones, name='facturas-importacion-historial'),
]