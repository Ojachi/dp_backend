from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from clientes.models import Cliente, ClienteSucursal

if TYPE_CHECKING:  # pragma: no cover
    from pagos.models import Pago

class Factura(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('parcial', 'Pago Parcial'),
        ('pagada', 'Pagada'),
        ('vencida', 'Vencida'),
        ('cancelada', 'Cancelada'),
    ]
    TIPOS_FACTURA = [
        ('FE', 'Factura Electrónica'),
        ('R', 'Remisión'),
    ]
    ESTADOS_ENTREGA = [
        ('pendiente', 'Pendiente por entregar'),
        ('entregado', 'Entregado'),
        ('devolucion_total', 'Devolución total'),
    ]
    
    numero_factura = models.CharField(max_length=50, unique=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='facturas')
    cliente_sucursal = models.ForeignKey(
        ClienteSucursal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='facturas'
    )
    vendedor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='facturas_vendedor')
    distribuidor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='facturas_distribuidor')
    tipo = models.CharField(max_length=2, choices=TIPOS_FACTURA, default='FE', help_text='Tipo de factura: FE (Factura Electrónica) o R (Remisión)')
    fecha_emision = models.DateField()
    fecha_vencimiento = models.DateField()
    valor_total = models.DecimalField(max_digits=12, decimal_places=2)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    estado_entrega = models.CharField(max_length=20, choices=ESTADOS_ENTREGA, default='pendiente')
    entrega_actualizado = models.DateTimeField(null=True, blank=True)
    entrega_actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='facturas_entrega_actualizadas'
    )
    observaciones = models.TextField(blank=True, null=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha_emision']
        indexes = [
            models.Index(fields=['numero_factura']),
            models.Index(fields=['cliente', 'estado']),
            models.Index(fields=['vendedor', 'estado']),
            models.Index(fields=['fecha_vencimiento']),
            models.Index(fields=['tipo']),
            models.Index(fields=['cliente_sucursal']),
        ]

    def __str__(self):
        return f"Factura {self.numero_factura} - {self.cliente.nombre}"
    
    def clean(self):
        """Validaciones del modelo"""
        # Validar que fecha de emisión no sea posterior a fecha de vencimiento
        if self.fecha_emision and self.fecha_vencimiento:
            if self.fecha_emision > self.fecha_vencimiento:
                raise ValidationError(
                    "La fecha de emisión no puede ser posterior a la fecha de vencimiento"
                )
        
        # Validar que el valor total sea positivo
        if self.valor_total is not None and self.valor_total <= 0:
            raise ValidationError("El valor total debe ser mayor a cero")
    
    @property
    def total_pagado(self):
        """Calcula el total pagado de esta factura"""
        # Considerar únicamente pagos confirmados
        pagos_qs = self.pagos.filter(estado='confirmado')  # type: ignore[attr-defined]
        total = pagos_qs.aggregate(
            total=models.Sum('valor_pagado')
        )['total'] or Decimal('0.00')
        return total
    
    @property
    def total_descuentos(self):
        """Suma de descuentos aplicados a la factura a través de pagos confirmados."""
        pagos_qs = self.pagos.filter(estado='confirmado')  # type: ignore[attr-defined]
        # Agregar por campo para evitar expresiones complejas
        dcto = pagos_qs.aggregate(total=models.Sum('descuento'))['total'] or Decimal('0.00')
        ica = pagos_qs.aggregate(total=models.Sum('ica'))['total'] or Decimal('0.00')
        rete = pagos_qs.aggregate(total=models.Sum('retencion'))['total'] or Decimal('0.00')
        nota = pagos_qs.aggregate(total=models.Sum('nota'))['total'] or Decimal('0.00')
        return dcto + ica + rete + nota

    @property
    def total_aplicado(self):
        """Total aplicado a la factura (pagos + descuentos confirmados)."""
        return self.total_pagado + self.total_descuentos
    
    @property
    def saldo_pendiente(self):
        """Calcula el saldo pendiente de la factura"""
        return self.valor_total - self.total_aplicado
    
    @property
    def esta_vencida(self):
        """Determina si la factura está vencida"""
        return (
            timezone.now().date() > self.fecha_vencimiento and 
            self.estado in ['pendiente', 'parcial', 'vencida']  # Incluye 'vencida' ya en BD
        )
    
    @property
    def dias_vencimiento(self):
        """Calcula los días de vencimiento (negativo si no ha vencido)"""
        delta = timezone.now().date() - self.fecha_vencimiento
        return delta.days
    
    def actualizar_estado(self):
        """Actualiza el estado de la factura basado en pagos y vencimiento"""
        estado_anterior = self.estado
        
        if self.saldo_pendiente <= Decimal('0.00'):
            self.estado = 'pagada'
        elif self.total_pagado > Decimal('0.00'):
            if self.esta_vencida:
                self.estado = 'vencida'  # Vencida con pago parcial
            else:
                self.estado = 'parcial'
        else:
            if self.esta_vencida:
                self.estado = 'vencida'
            else:
                self.estado = 'pendiente'
        
        # Solo guardar si el estado cambió
        if estado_anterior != self.estado:
            self.save(update_fields=['estado'])
    
    @classmethod
    def actualizar_estados_vencidas(cls):
        """Método para actualizar masivamente facturas vencidas"""
        from django.utils import timezone
        
        # Obtener facturas que deberían estar vencidas pero no lo están
        facturas_a_vencer = cls.objects.filter(
            fecha_vencimiento__lt=timezone.now().date(),
            estado__in=['pendiente', 'parcial']
        ).exclude(estado='vencida')
        
        # Actualizar sus estados
        count = 0
        for factura in facturas_a_vencer:
            factura.actualizar_estado()
            count += 1
        
        return count
    
    def puede_recibir_pago(self, monto):
        """Valida si puede recibir un pago por el monto especificado"""
        if self.estado == 'cancelada':
            return False, "No se pueden registrar pagos en facturas canceladas"
        
        if self.estado == 'pagada':
            return False, "La factura ya está completamente pagada"
            
        if monto <= 0:
            return False, "El monto del pago debe ser mayor a cero"
            
        if monto > self.saldo_pendiente:
            return False, f"El monto excede el saldo pendiente de {self.saldo_pendiente}"
            
        return True, "Pago válido"

    
