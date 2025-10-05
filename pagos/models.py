from django.db import models
from facturas.models import Factura
from django.conf import settings

class Pago(models.Model):
    factura = models.ForeignKey(Factura, on_delete=models.CASCADE, related_name='pagos')
    fecha_pago = models.DateTimeField()
    valor_pagado = models.DecimalField(max_digits=12, decimal_places=2)
    tipo_pago = models.CharField(max_length=30)
    comprobante = models.FileField(upload_to='comprobantes/', blank=True, null=True)
    notas = models.TextField(blank=True, null=True)
    usuario_registro = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Pago {self.id} - Factura {self.factura.numero_factura}"
