from django.db import models
from django.conf import settings
from facturas.models import Factura

class TipoAlerta(models.Model):
    """Tipos de alertas configurables"""
    TIPOS_ALERTAS = [
        ('vencimiento', 'Vencimiento de Factura'),
        ('pago_parcial', 'Pago Parcial Recibido'),
        ('sin_pagos', 'Sin Pagos por Tiempo Prolongado'),
        ('monto_alto', 'Factura de Monto Alto'),
        ('custom', 'Personalizada'),
    ]
    
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=TIPOS_ALERTAS)
    descripcion = models.TextField()
    activa = models.BooleanField(default=True)
    
    # Configuraciones para alertas de vencimiento
    dias_anticipacion = models.IntegerField(null=True, blank=True, 
                                          help_text="Días antes del vencimiento para alertar")
    
    # Configuraciones para alertas de monto
    monto_minimo = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                     help_text="Monto mínimo para generar alerta")
    
    # Configuraciones para alertas de tiempo
    dias_sin_actividad = models.IntegerField(null=True, blank=True,
                                           help_text="Días sin actividad para alertar")
    
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Tipo de Alerta"
        verbose_name_plural = "Tipos de Alertas"
    
    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()})"

class Alerta(models.Model):
    """Alertas generadas automáticamente"""
    PRIORIDADES = [
        ('baja', 'Baja'),
        ('media', 'Media'),
        ('alta', 'Alta'),
        ('critica', 'Crítica'),
    ]
    
    ESTADOS = [
        ('nueva', 'Nueva'),
        ('leida', 'Leída'),
        ('procesada', 'Procesada'),
        ('descartada', 'Descartada'),
    ]
    
    tipo_alerta = models.ForeignKey(TipoAlerta, on_delete=models.CASCADE, related_name='alertas')
    factura = models.ForeignKey(Factura, on_delete=models.CASCADE, related_name='alertas')
    usuario_destinatario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                           related_name='alertas_recibidas', 
                                           help_text="Usuario que debe ver esta alerta")
    
    titulo = models.CharField(max_length=200)
    mensaje = models.TextField()
    prioridad = models.CharField(max_length=10, choices=PRIORIDADES, default='media')
    estado = models.CharField(max_length=15, choices=ESTADOS, default='nueva')
    
    # Metadatos
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    fecha_leida = models.DateTimeField(null=True, blank=True)
    fecha_procesada = models.DateTimeField(null=True, blank=True)
    usuario_procesado = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name='alertas_procesadas')
    
    # Datos adicionales en JSON para flexibilidad
    datos_contexto = models.JSONField(default=dict, blank=True,
                                    help_text="Datos adicionales sobre la alerta")
    
    class Meta:
        ordering = ['-fecha_generacion']
        indexes = [
            models.Index(fields=['usuario_destinatario', 'estado']),
            models.Index(fields=['factura', 'estado']),
            models.Index(fields=['prioridad', 'fecha_generacion']),
        ]
    
    def __str__(self):
        return f"{self.titulo} - {self.factura.numero_factura}"
    
    def marcar_como_leida(self, usuario=None):
        """Marcar alerta como leída"""
        if self.estado == 'nueva':
            self.estado = 'leida'
            from django.utils import timezone
            self.fecha_leida = timezone.now()
            self.save(update_fields=['estado', 'fecha_leida'])
    
    def procesar(self, usuario):
        """Marcar alerta como procesada"""
        self.estado = 'procesada'
        from django.utils import timezone
        self.fecha_procesada = timezone.now()
        self.usuario_procesado = usuario
        self.save(update_fields=['estado', 'fecha_procesada', 'usuario_procesado'])
    
    def descartar(self):
        """Descartar alerta"""
        self.estado = 'descartada'
        self.save(update_fields=['estado'])

class ConfiguracionAlerta(models.Model):
    """Configuración personalizada de alertas por usuario"""
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='configuracion_alertas')
    tipo_alerta = models.ForeignKey(TipoAlerta, on_delete=models.CASCADE)
    
    # Configuración personalizada
    recibir_email = models.BooleanField(default=False)
    recibir_notificacion = models.BooleanField(default=True)
    
    # Override de configuraciones del tipo de alerta
    dias_anticipacion_custom = models.IntegerField(null=True, blank=True)
    monto_minimo_custom = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    activa = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['usuario', 'tipo_alerta']
        verbose_name = "Configuración de Alerta"
        verbose_name_plural = "Configuraciones de Alertas"
    
    def __str__(self):
        return f"{self.usuario.name} - {self.tipo_alerta.nombre}"
