from django.db import models
from django.conf import settings

class Cliente(models.Model):
    nombre = models.CharField(max_length=100)
    direccion = models.CharField(max_length=200, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    creador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre


class Poblacion(models.Model):
    """Lugares donde se ubican tiendas/almacenes de clientes.
    Cada población tiene asignados un vendedor y un distribuidor responsables.
    """
    nombre = models.CharField(max_length=120, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    vendedor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='poblaciones_vendedor'
    )
    distribuidor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='poblaciones_distribuidor'
    )
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Población'
        verbose_name_plural = 'Poblaciones'

    def __str__(self):
        return self.nombre


class ClienteSucursal(models.Model):
    """Sucursal/Tienda del cliente con código por población.
    Un cliente puede tener varias sucursales (mismo municipio u otros). El código
    es único por cliente y población.
    """
    CONDICION_PAGO_CHOICES = [
        ('contado', 'Contado'),
        ('15d', '15 días'),
        ('10d', '10 días'),
        ('5d', '5 días'),
        # Nota: mantenemos '30d' para compatibilidad con datos existentes, pero no lo exponemos en el UI
        ('30d', '30 días'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='sucursales')
    poblacion = models.ForeignKey(Poblacion, on_delete=models.CASCADE, related_name='sucursales')
    codigo = models.CharField(max_length=50, unique=True)
    condicion_pago = models.CharField(max_length=10, choices=CONDICION_PAGO_CHOICES, default='contado')
    direccion = models.CharField(max_length=200, blank=True, null=True)
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['poblacion']),
            models.Index(fields=['cliente']),
        ]
        verbose_name = 'Sucursal de Cliente'
        verbose_name_plural = 'Sucursales de Clientes'

    def __str__(self):
        return f"{self.cliente.nombre} - {self.poblacion.nombre} [{self.codigo}]"
