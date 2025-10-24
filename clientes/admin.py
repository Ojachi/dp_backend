from django.contrib import admin
from .models import Cliente, Poblacion, ClienteSucursal

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
	list_display = ("nombre", "telefono", "email", "creado")
	search_fields = ("nombre", "telefono", "email")

@admin.register(Poblacion)
class PoblacionAdmin(admin.ModelAdmin):
	list_display = ("nombre", "vendedor", "distribuidor")
	search_fields = ("nombre",)

@admin.register(ClienteSucursal)
class ClienteSucursalAdmin(admin.ModelAdmin):
	list_display = ("cliente", "poblacion", "codigo", "condicion_pago", "activo")
	list_filter = ("poblacion", "condicion_pago", "activo")
	search_fields = ("cliente__nombre", "codigo", "poblacion__nombre")
