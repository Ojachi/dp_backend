from django.urls import path

from . import views

urlpatterns = [
    path("cuentas-por-cobrar/", views.cuentas_por_cobrar, name="cartera-cuentas-por-cobrar"),
]
