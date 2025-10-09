from django.urls import path
from . import views

urlpatterns = [
    # CRUD de vendedores
    path('', views.VendedorListCreateView.as_view(), name='vendedores-list-create'),
    path('<int:pk>/', views.VendedorDetailView.as_view(), name='vendedor-detail'),
    
    # Endpoints especiales
    path('estadisticas/', views.estadisticas_vendedores, name='estadisticas-vendedores'),
    path('mi-perfil/', views.mi_perfil_vendedor, name='mi-perfil-vendedor'),
]
