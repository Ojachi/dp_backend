from django.urls import path
from . import views

urlpatterns = [
    # CRUD de distribuidores
    path('', views.DistribuidorListCreateView.as_view(), name='distribuidores-list-create'),
    path('<int:pk>/', views.DistribuidorDetailView.as_view(), name='distribuidor-detail'),
    
    # Endpoints especiales
    path('estadisticas/', views.estadisticas_distribuidores, name='estadisticas-distribuidores'),
    path('mi-perfil/', views.mi_perfil_distribuidor, name='mi-perfil-distribuidor'),
]
