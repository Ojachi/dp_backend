from django.urls import path
from .views import VendedorListCreateView, VendedorRetrieveUpdateDestroyView

urlpatterns = [
    path('', VendedorListCreateView.as_view(), name='vendedores-list-create'),
    path('<int:pk>/', VendedorRetrieveUpdateDestroyView.as_view(), name='vendedor-detail'),
]
