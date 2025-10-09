from django.urls import path
from . import views

urlpatterns = [
    # CRUD de facturas
    path('', views.FacturaListCreateView.as_view(), name='factura-list-create'),
    path('<int:pk>/', views.FacturaDetailView.as_view(), name='factura-detail'),
    
    # Endpoints especiales
    path('vencidas/', views.facturas_vencidas, name='facturas-vencidas'),
    path('dashboard/', views.dashboard_facturas, name='dashboard-facturas'),
    path('importar/', views.importar_facturas_excel, name='importar-facturas'),
]