from django.urls import path
from . import views

urlpatterns = [
    # CRUD de pagos
    path('', views.PagoListCreateView.as_view(), name='pago-list-create'),
    path('<int:pk>/', views.PagoDetailView.as_view(), name='pago-detail'),
    path('<int:pk>/confirmar/', views.confirmar_pago, name='pago-confirmar'),
    path('metodos/', views.listar_metodos_pago, name='pagos-metodos'),
    path('cuentas/', views.CuentaPagoListCreateView.as_view(), name='pagos-cuentas'),
    path('cuentas/<int:pk>/', views.CuentaPagoDetailView.as_view(), name='pagos-cuentas-detalle'),
    path('exportar/', views.exportar_pagos, name='pagos-exportar'),
    
    # Endpoints especiales
    path('factura/<int:factura_id>/', views.historial_pagos_factura, name='historial-pagos-factura'),
    path('facturas/<int:factura_id>/pagos/', views.registrar_pago_factura, name='factura-registrar-pago'),
    path('cliente/<int:cliente_id>/resumen/', views.resumen_pagos_cliente, name='resumen-pagos-cliente'),
    path('dashboard/', views.dashboard_pagos, name='dashboard-pagos'),
]