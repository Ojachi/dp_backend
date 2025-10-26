from django.urls import path
from . import views

urlpatterns = [
    # Gestión de alertas del usuario
    path('', views.AlertaListView.as_view(), name='alerta-list'),
    path('<int:pk>/', views.AlertaDetailView.as_view(), name='alerta-detail'),
    path('<int:pk>/marcar-leida/', views.marcar_alerta_estado, name='alerta-marcar-leida'),
    path('contador/', views.contador_alertas, name='contador-alertas'),
    path('recientes/', views.alertas_recientes, name='alertas-recientes'),
    
    # Gestión administrativa (solo gerentes)
    path('estadisticas/', views.estadisticas_alertas, name='estadisticas-alertas'),
    
    # Tipos de alertas (solo gerentes)
    path('tipos/', views.TipoAlertaListCreateView.as_view(), name='tipo-alerta-list'),
    path('tipos/<int:pk>/', views.TipoAlertaDetailView.as_view(), name='tipo-alerta-detail'),
    
    # Configuraciones personales
    path('configuracion/', views.ConfiguracionAlertaListView.as_view(), name='configuracion-alerta-list'),
    path('configuracion/<int:pk>/', views.ConfiguracionAlertaDetailView.as_view(), name='configuracion-alerta-detail'),
]