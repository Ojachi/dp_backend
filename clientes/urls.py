from django.urls import path
from .views import ClienteListCreateView, ClienteRetrieveUpdateDestroyView

urlpatterns = [
    path('', ClienteListCreateView.as_view(), name='clientes-list-create'),
    path('<int:pk>/', ClienteRetrieveUpdateDestroyView.as_view(), name='cliente-detail'),
]
