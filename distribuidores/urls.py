from django.urls import path
from . import views

urlpatterns = [
    # CRUD de distribuidores
    path('', views.DistribuidorListCreateView.as_view(), name='distribuidores-list-create'),
    path('<int:pk>/', views.DistribuidorDetailView.as_view(), name='distribuidor-detail'),
]
