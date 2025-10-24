from django.contrib import admin
from .models import Pago, CuentaPago

@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
	list_display = ("id", "codigo", "factura", "valor_pagado", "tipo_pago", "estado", "usuario_registro", "fecha_pago")
	search_fields = ("codigo", "factura__numero_factura", "usuario_registro__first_name", "usuario_registro__last_name")
	list_filter = ("tipo_pago", "estado")

@admin.register(CuentaPago)
class CuentaPagoAdmin(admin.ModelAdmin):
	list_display = ("nombre", "banco", "numero", "activo")
	list_filter = ("activo",)
	search_fields = ("nombre", "banco", "numero")
