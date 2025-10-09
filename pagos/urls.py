from django.urls import path
from . import views

urlpatterns = [
    # CRUD de pagos
    path('', views.PagoListCreateView.as_view(), name='pago-list-create'),
    path('<int:pk>/', views.PagoDetailView.as_view(), name='pago-detail'),
    
    # Endpoints especiales
    path('factura/<int:factura_id>/', views.historial_pagos_factura, name='historial-pagos-factura'),
    path('cliente/<int:cliente_id>/resumen/', views.resumen_pagos_cliente, name='resumen-pagos-cliente'),
    path('dashboard/', views.dashboard_pagos, name='dashboard-pagos'),
]