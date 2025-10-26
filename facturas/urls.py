from django.urls import path

from . import views

urlpatterns = [
    # CRUD de facturas
    path('', views.FacturaListCreateView.as_view(), name='factura-list-create'),
    path('<int:pk>/', views.FacturaDetailView.as_view(), name='factura-detail'),
]