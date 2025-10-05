from django.db import models
from clientes.models import Cliente
from django.conf import settings

class Factura(models.Model):
    numero_factura = models.CharField(max_length=50, unique=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='facturas')
    vendedor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='facturas_vendedor')
    distribuidor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='facturas_distribuidor')
    fecha_emision = models.DateField()
    fecha_vencimiento = models.DateField()
    valor_total = models.DecimalField(max_digits=12, decimal_places=2)
    estado = models.CharField(max_length=20, default='pendiente')
    observaciones = models.TextField(blank=True, null=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Factura {self.numero_factura} - {self.cliente.nombre}"
