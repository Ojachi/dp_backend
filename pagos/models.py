from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from facturas.models import Factura
from django.conf import settings

class Pago(models.Model):
    TIPOS_PAGO = [
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia'),
        ('cheque', 'Cheque'),
        ('tarjeta_credito', 'Tarjeta de Crédito'),
        ('tarjeta_debito', 'Tarjeta de Débito'),
        ('consignacion', 'Consignación'),
        ('otro', 'Otro'),
    ]
    
    factura = models.ForeignKey(Factura, on_delete=models.CASCADE, related_name='pagos')
    fecha_pago = models.DateTimeField(default=timezone.now)
    valor_pagado = models.DecimalField(max_digits=12, decimal_places=2)
    tipo_pago = models.CharField(max_length=30, choices=TIPOS_PAGO, default='efectivo')
    comprobante = models.FileField(upload_to='comprobantes/%Y/%m/', blank=True, null=True)
    numero_comprobante = models.CharField(max_length=100, blank=True, null=True, 
                                        help_text="Número de referencia del comprobante")
    notas = models.TextField(blank=True, null=True)
    usuario_registro = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha_pago']
        indexes = [
            models.Index(fields=['factura', 'fecha_pago']),
            models.Index(fields=['usuario_registro', 'fecha_pago']),
            models.Index(fields=['tipo_pago']),
        ]

    def __str__(self):
        return f"Pago {self.id} - Factura {self.factura.numero_factura} - ${self.valor_pagado}"
    
    def clean(self):
        """Validaciones del modelo"""
        if self.valor_pagado <= 0:
            raise ValidationError("El valor del pago debe ser mayor a cero")
        
        # Validar que fecha de pago no sea futura
        if self.fecha_pago and self.fecha_pago.date() > timezone.now().date():
            raise ValidationError("La fecha de pago no puede ser futura")
        
        # Validar que no se exceda el saldo pendiente de la factura
        if self.factura_id:
            saldo_actual = self.factura.valor_total
            pagos_existentes = self.factura.pagos.exclude(pk=self.pk).aggregate(
                total=models.Sum('valor_pagado')
            )['total'] or Decimal('0.00')
            
            saldo_disponible = saldo_actual - pagos_existentes
            
            if self.valor_pagado > saldo_disponible:
                raise ValidationError(
                    f"El pago de ${self.valor_pagado} excede el saldo pendiente de ${saldo_disponible}"
                )
    
    def save(self, *args, **kwargs):
        """Override save para validar y actualizar estado de factura"""
        self.full_clean()  # Ejecutar validaciones
        super().save(*args, **kwargs)
        
        # Actualizar el estado de la factura después de guardar el pago
        self.factura.actualizar_estado()
    
    def delete(self, *args, **kwargs):
        """Override delete para actualizar estado de factura al eliminar pago"""
        factura = self.factura
        super().delete(*args, **kwargs)
        factura.actualizar_estado()
