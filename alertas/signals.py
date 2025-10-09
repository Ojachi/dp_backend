# Sistema de alertas automáticas con Django Signals
# alertas/signals.py

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from facturas.models import Factura
from pagos.models import Pago
from .services import ServicioAlertas
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Factura)
def generar_alertas_factura_cambios(sender, instance, created, **kwargs):
    """
    Generar alertas automáticamente cuando cambia una factura
    Se ejecuta inmediatamente cuando:
    - Se crea una nueva factura
    - Se actualiza el estado de una factura
    """
    try:
        # Si es una nueva factura, verificar si necesita alerta inmediata
        if created:
            # Verificar si la factura ya está vencida al crearse
            if instance.fecha_vencimiento < timezone.now().date():
                logger.info(f"Factura {instance.numero_factura} creada ya vencida - generando alerta")
                ServicioAlertas.generar_alerta_factura_especifica(instance, tipo='vencida')
            
            # Verificar si es un monto alto
            elif instance.valor_total > 1000000:  # Configurable
                logger.info(f"Factura {instance.numero_factura} con monto alto - generando alerta")
                ServicioAlertas.generar_alerta_factura_especifica(instance, tipo='monto_alto')
        
        # Si cambió el estado a 'vencida', generar alerta inmediata
        if instance.estado == 'vencida':
            ServicioAlertas.generar_alerta_factura_especifica(instance, tipo='vencida')
            logger.info(f"Alerta generada automáticamente para factura vencida: {instance.numero_factura}")
    
    except Exception as e:
        logger.error(f"Error generando alertas para factura {instance.numero_factura}: {str(e)}")

@receiver(post_save, sender=Pago)
def generar_alertas_pago_realizado(sender, instance, created, **kwargs):
    """
    Generar alertas automáticamente cuando se registra un pago
    """
    try:
        if created:
            factura = instance.factura
            
            # Si el pago completa la factura, eliminar alertas de vencimiento
            if factura.estado == 'pagada':
                # Marcar como resueltas las alertas de vencimiento de esta factura
                from .models import Alerta
                Alerta.objects.filter(
                    factura=factura,
                    tipo_alerta__tipo='vencimiento',
                    estado__in=['nueva', 'leida']
                ).update(estado='resuelta')
                
                logger.info(f"Alertas de vencimiento resueltas para factura pagada: {factura.numero_factura}")
    
    except Exception as e:
        logger.error(f"Error procesando alertas para pago de factura {instance.factura.numero_factura}: {str(e)}")

@receiver(pre_save, sender=Factura)
def detectar_cambios_factura(sender, instance, **kwargs):
    """
    Detectar cambios en facturas para generar alertas apropiadas
    """
    if instance.pk:  # Solo si ya existe
        try:
            factura_anterior = Factura.objects.get(pk=instance.pk)
            
            # Si cambió de un estado normal a 'vencida'
            if (factura_anterior.estado != 'vencida' and 
                instance.estado == 'vencida'):
                
                # Marcar para generar alerta después del save
                instance._generar_alerta_vencimiento = True
        
        except Factura.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"Error detectando cambios en factura {instance.numero_factura}: {str(e)}")