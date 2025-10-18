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
    ESTADOS = [
        ('registrado', 'Registrado'),  # Registrado por cualquier rol, aún no aplicado
        ('confirmado', 'Confirmado'),  # Confirmado y aplicado por Gerente
        ('anulado', 'Anulado'),        # Anulado (opcional para futuro)
    ]
    
    factura = models.ForeignKey(Factura, on_delete=models.CASCADE, related_name='pagos')
    fecha_pago = models.DateTimeField(default=timezone.now)
    valor_pagado = models.DecimalField(max_digits=12, decimal_places=2)
    tipo_pago = models.CharField(max_length=30, choices=TIPOS_PAGO, default='efectivo')
    comprobante = models.FileField(upload_to='comprobantes/%Y/%m/', blank=True, null=True)
    numero_comprobante = models.CharField(max_length=100, blank=True, null=True, 
                                        help_text="Número de referencia del comprobante")
    notas = models.TextField(blank=True, null=True)
    # Descuentos aplicables a la factura (no al pago), registrados junto con este pago
    descuento = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    ica = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    retencion = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    nota = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    usuario_registro = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    # Nuevo flujo de confirmación
    estado = models.CharField(max_length=20, choices=ESTADOS, default='registrado')
    usuario_confirmacion = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pagos_confirmados'
    )
    fecha_confirmacion = models.DateTimeField(null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha_pago']
        indexes = [
            models.Index(fields=['factura', 'fecha_pago']),
            models.Index(fields=['usuario_registro', 'fecha_pago']),
            models.Index(fields=['tipo_pago']),
            models.Index(fields=['estado']),
        ]

    def __str__(self):
        return f"Pago {self.id} - Factura {self.factura.numero_factura} - ${self.valor_pagado}"  # type: ignore[attr-defined]
    
    def clean(self):
        """Validaciones del modelo"""
        # Permitir valor_pagado = 0 si hay descuentos/retenciones/ICA/nota que aplicar
        # Se validará que el total aplicado sea > 0 más abajo
        for campo in ('descuento', 'ica', 'retencion', 'nota'):
            valor = getattr(self, campo) or 0
            if valor < 0:
                raise ValidationError(f"El campo {campo} no puede ser negativo")
        
        # Validar que fecha de pago no sea futura
        if self.fecha_pago and self.fecha_pago.date() > timezone.now().date():
            raise ValidationError("La fecha de pago no puede ser futura")
        
        # Calcular total a aplicar (independiente del estado) para validar no-cero
        total_aplicar_actual = (
            (self.valor_pagado or Decimal('0.00')) +
            (self.descuento or Decimal('0.00')) +
            (self.ica or Decimal('0.00')) +
            (self.retencion or Decimal('0.00')) +
            (self.nota or Decimal('0.00'))
        )
        if total_aplicar_actual <= 0:
            raise ValidationError("Debe indicar al menos un valor a aplicar (pago, descuento, retención, ICA o nota)")

        # Si el pago se encuentra confirmado (o será confirmado en este guardado), validar no exceder saldo
        if self.factura_id and self.estado == 'confirmado':  # type: ignore[attr-defined]
            saldo_actual = self.factura.valor_total
            pagos_confirmados_existentes = self.factura.pagos.exclude(pk=self.pk).filter(  # type: ignore[attr-defined]
                estado='confirmado'
            )
            total_pagado_existente = pagos_confirmados_existentes.aggregate(total=models.Sum('valor_pagado'))['total'] or Decimal('0.00')
            total_descuentos_existentes = (
                (pagos_confirmados_existentes.aggregate(total=models.Sum('descuento'))['total'] or Decimal('0.00')) +
                (pagos_confirmados_existentes.aggregate(total=models.Sum('ica'))['total'] or Decimal('0.00')) +
                (pagos_confirmados_existentes.aggregate(total=models.Sum('retencion'))['total'] or Decimal('0.00')) +
                (pagos_confirmados_existentes.aggregate(total=models.Sum('nota'))['total'] or Decimal('0.00'))
            )

            aplicado_existente = total_pagado_existente + total_descuentos_existentes
            aplicado_nuevo = (
                (self.valor_pagado or Decimal('0.00')) +
                (self.descuento or Decimal('0.00')) +
                (self.ica or Decimal('0.00')) +
                (self.retencion or Decimal('0.00')) +
                (self.nota or Decimal('0.00'))
            )
            total_aplicado = aplicado_existente + aplicado_nuevo

            if total_aplicado > saldo_actual:
                excede = total_aplicado - saldo_actual
                raise ValidationError(
                    f"El total aplicado (pago + descuentos) excede el saldo de la factura por ${excede}"
                )
    
    def save(self, *args, **kwargs):
        """Override save para validar y actualizar estado de factura"""
        self.full_clean()  # Ejecutar validaciones
        super().save(*args, **kwargs)
        
        # Actualizar el estado de la factura solo cuando el pago esté confirmado
        if self.estado == 'confirmado':
            self.factura.actualizar_estado()
    
    def delete(self, *args, **kwargs):
        """Override delete para actualizar estado de factura al eliminar pago"""
        factura = self.factura
        result = super().delete(*args, **kwargs)
        # Solo requiere actualización si el pago era confirmado y afectaba saldo
        factura.actualizar_estado()
        return result
