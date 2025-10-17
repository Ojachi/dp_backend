from django.urls import path

from . import views

urlpatterns = [
    path("resumen/", views.resumen_cartera, name="cartera-resumen"),
    path("cuentas-por-cobrar/", views.cuentas_por_cobrar, name="cartera-cuentas-por-cobrar"),
    path("clientes/<int:cliente_id>/detalle/", views.detalle_cuenta, name="cartera-detalle-cuenta"),
    path(
        "clientes/<int:cliente_id>/gestiones/",
        views.registrar_gestion_cobranza,
        name="cartera-registrar-gestion",
    ),
    path(
        "clientes/<int:cliente_id>/historial-gestiones/",
        views.historial_gestiones_view,
        name="cartera-historial-gestiones",
    ),
    path(
        "clientes/<int:cliente_id>/limite/",
        views.actualizar_limite,
        name="cartera-actualizar-limite",
    ),
    path(
        "clientes/<int:cliente_id>/enviar-estado/",
        views.enviar_estado_cuenta,
        name="cartera-enviar-estado",
    ),
    path("estadisticas/mora/", views.estadisticas_mora, name="cartera-estadisticas-mora"),
    path("proyeccion/", views.proyeccion_cobranza_view, name="cartera-proyeccion-cobranza"),
]
