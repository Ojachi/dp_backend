from django.contrib import admin

from .models import EnvioEstadoCuenta, GestionCobranza, PerfilCreditoCliente


@admin.register(PerfilCreditoCliente)
class PerfilCreditoClienteAdmin(admin.ModelAdmin):
    list_display = ("cliente", "limite_credito", "dias_promedio_cobranza", "porcentaje_mora", "actualizado")
    search_fields = ("cliente__nombre",)


@admin.register(GestionCobranza)
class GestionCobranzaAdmin(admin.ModelAdmin):
    list_display = ("cliente", "tipo", "resultado", "proximo_contacto", "creado")
    list_filter = ("tipo", "resultado")
    search_fields = ("cliente__nombre", "observaciones")


@admin.register(EnvioEstadoCuenta)
class EnvioEstadoCuentaAdmin(admin.ModelAdmin):
    list_display = ("cliente", "estado", "medio", "creado", "enviado_en")
    list_filter = ("estado", "medio")
    search_fields = ("cliente__nombre", "detalle")
