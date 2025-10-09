from django.db import models
from django.utils import timezone
from decimal import Decimal
from clientes.models import Cliente
from django.conf import settings

class Factura(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('parcial', 'Pago Parcial'),
        ('pagada', 'Pagada'),
        ('vencida', 'Vencida'),
        ('cancelada', 'Cancelada'),
    ]
    
    numero_factura = models.CharField(max_length=50, unique=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='facturas')
    vendedor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='facturas_vendedor')
    distribuidor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='facturas_distribuidor')
    fecha_emision = models.DateField()
    fecha_vencimiento = models.DateField()
    valor_total = models.DecimalField(max_digits=12, decimal_places=2)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
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
        ]

    def __str__(self):
        return f"Factura {self.numero_factura} - {self.cliente.nombre}"
    
    @property
    def total_pagado(self):
        """Calcula el total pagado de esta factura"""
        total = self.pagos.aggregate(
            total=models.Sum('valor_pagado')
        )['total'] or Decimal('0.00')
        return total
    
    @property
    def saldo_pendiente(self):
        """Calcula el saldo pendiente de la factura"""
        return self.valor_total - self.total_pagado
    
    @property
    def esta_vencida(self):
        """Determina si la factura está vencida"""
        return (
            timezone.now().date() > self.fecha_vencimiento and 
            self.estado in ['pendiente', 'parcial']
        )
    
    @property
    def dias_vencimiento(self):
        """Calcula los días de vencimiento (negativo si no ha vencido)"""
        delta = timezone.now().date() - self.fecha_vencimiento
        return delta.days
    
    def actualizar_estado(self):
        """Actualiza el estado de la factura basado en pagos"""
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
        self.save(update_fields=['estado'])
    
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
