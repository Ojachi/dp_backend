from django.urls import path
from .views import DistribuidorListCreateView, DistribuidorRetrieveUpdateDestroyView

urlpatterns = [
    path('', DistribuidorListCreateView.as_view(), name='distribuidores-list-create'),
    path('<int:pk>/', DistribuidorRetrieveUpdateDestroyView.as_view(), name='distribuidor-detail'),
]
