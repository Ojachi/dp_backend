from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from decimal import Decimal

from .models import Alerta, TipoAlerta, ConfiguracionAlerta
from facturas.models import Factura


class ServicioAlertas:
    """Servicio para generar y gestionar alertas automáticas"""
    
    @classmethod
    def generar_alertas_vencimiento(cls):
        """Generar alertas para facturas próximas a vencer"""
        tipos_vencimiento = TipoAlerta.objects.filter(
            tipo='vencimiento', 
            activa=True
        )
        
        alertas_generadas = 0
        
        for tipo_alerta in tipos_vencimiento:
            dias_anticipacion = tipo_alerta.dias_anticipacion or 7
            fecha_limite = timezone.now().date() + timedelta(days=dias_anticipacion)
            
            # Buscar facturas que vencen en el período especificado
            facturas_por_vencer = Factura.objects.filter(
                fecha_vencimiento__lte=fecha_limite,
                fecha_vencimiento__gte=timezone.now().date(),
                estado__in=['pendiente', 'parcial']
            ).exclude(
                # Excluir facturas que ya tienen alertas de este tipo
                alertas__tipo_alerta=tipo_alerta,
                alertas__estado__in=['nueva', 'leida']
            )
            
            for factura in facturas_por_vencer:
                # Determinar usuarios que deben recibir la alerta
                usuarios_destinatarios = cls._obtener_usuarios_destinatarios(factura, tipo_alerta)
                
                for usuario in usuarios_destinatarios:
                    dias_restantes = (factura.fecha_vencimiento - timezone.now().date()).days
                    
                    if dias_restantes <= 0:
                        titulo = f"VENCIDA: Factura {factura.numero_factura}"
                        prioridad = 'critica'
                        mensaje = f"La factura {factura.numero_factura} del cliente {factura.cliente.nombre} venció hace {abs(dias_restantes)} días. Saldo pendiente: ${factura.saldo_pendiente}"
                    else:
                        titulo = f"Por vencer: Factura {factura.numero_factura}"
                        prioridad = 'alta' if dias_restantes <= 3 else 'media'
                        mensaje = f"La factura {factura.numero_factura} del cliente {factura.cliente.nombre} vence en {dias_restantes} días. Saldo pendiente: ${factura.saldo_pendiente}"
                    
                    alerta = Alerta.objects.create(
                        tipo_alerta=tipo_alerta,
                        factura=factura,
                        usuario_destinatario=usuario,
                        titulo=titulo,
                        mensaje=mensaje,
                        prioridad=prioridad,
                        datos_contexto={
                            'dias_restantes': dias_restantes,
                            'saldo_pendiente': str(factura.saldo_pendiente),
                            'cliente_id': factura.cliente.id,
                            'cliente_nombre': factura.cliente.nombre,
                        }
                    )
                    alertas_generadas += 1
        
        return alertas_generadas
    
    @classmethod
    def generar_alertas_montos_altos(cls):
        """Generar alertas para facturas de montos altos"""
        tipos_monto = TipoAlerta.objects.filter(
            tipo='monto_alto',
            activa=True,
            monto_minimo__isnull=False
        )
        
        alertas_generadas = 0
        
        for tipo_alerta in tipos_monto:
            # Buscar facturas creadas recientemente con montos altos
            fecha_desde = timezone.now() - timedelta(days=1)  # Últimas 24 horas
            
            facturas_monto_alto = Factura.objects.filter(
                valor_total__gte=tipo_alerta.monto_minimo,
                creado__gte=fecha_desde
            ).exclude(
                # Excluir facturas que ya tienen alertas de este tipo
                alertas__tipo_alerta=tipo_alerta,
                alertas__estado__in=['nueva', 'leida']
            )
            
            for factura in facturas_monto_alto:
                usuarios_destinatarios = cls._obtener_usuarios_destinatarios(factura, tipo_alerta)
                
                for usuario in usuarios_destinatarios:
                    alerta = Alerta.objects.create(
                        tipo_alerta=tipo_alerta,
                        factura=factura,
                        usuario_destinatario=usuario,
                        titulo=f"Factura de monto alto: {factura.numero_factura}",
                        mensaje=f"Nueva factura {factura.numero_factura} del cliente {factura.cliente.nombre} por valor de ${factura.valor_total}",
                        prioridad='media',
                        datos_contexto={
                            'valor_factura': str(factura.valor_total),
                            'monto_limite': str(tipo_alerta.monto_minimo),
                            'cliente_id': factura.cliente.id,
                            'cliente_nombre': factura.cliente.nombre,
                        }
                    )
                    alertas_generadas += 1
        
        return alertas_generadas
    
    @classmethod
    def generar_alertas_sin_pagos(cls):
        """Generar alertas para facturas sin pagos por tiempo prolongado"""
        tipos_sin_pagos = TipoAlerta.objects.filter(
            tipo='sin_pagos',
            activa=True,
            dias_sin_actividad__isnull=False
        )
        
        alertas_generadas = 0
        
        for tipo_alerta in tipos_sin_pagos:
            fecha_limite = timezone.now().date() - timedelta(days=tipo_alerta.dias_sin_actividad)
            
            # Buscar facturas antiguas sin pagos
            facturas_sin_pagos = Factura.objects.filter(
                fecha_emision__lte=fecha_limite,
                estado__in=['pendiente'],
                pagos__isnull=True
            ).exclude(
                # Excluir facturas que ya tienen alertas de este tipo recientes
                alertas__tipo_alerta=tipo_alerta,
                alertas__estado__in=['nueva', 'leida'],
                alertas__fecha_generacion__gte=timezone.now() - timedelta(days=7)
            ).distinct()
            
            for factura in facturas_sin_pagos:
                usuarios_destinatarios = cls._obtener_usuarios_destinatarios(factura, tipo_alerta)
                
                dias_sin_pago = (timezone.now().date() - factura.fecha_emision).days
                
                for usuario in usuarios_destinatarios:
                    alerta = Alerta.objects.create(
                        tipo_alerta=tipo_alerta,
                        factura=factura,
                        usuario_destinatario=usuario,
                        titulo=f"Sin pagos: Factura {factura.numero_factura}",
                        mensaje=f"La factura {factura.numero_factura} del cliente {factura.cliente.nombre} lleva {dias_sin_pago} días sin recibir pagos. Valor: ${factura.valor_total}",
                        prioridad='media',
                        datos_contexto={
                            'dias_sin_pago': dias_sin_pago,
                            'valor_factura': str(factura.valor_total),
                            'cliente_id': factura.cliente.id,
                            'cliente_nombre': factura.cliente.nombre,
                        }
                    )
                    alertas_generadas += 1
        
        return alertas_generadas
    
    @classmethod
    def _obtener_usuarios_destinatarios(cls, factura, tipo_alerta):
        """Determinar qué usuarios deben recibir una alerta específica"""
        usuarios = []
        
        # Configuraciones personalizadas de usuarios
        configuraciones_activas = ConfiguracionAlerta.objects.filter(
            tipo_alerta=tipo_alerta,
            activa=True,
            recibir_notificacion=True
        ).select_related('usuario')
        
        # Si hay configuraciones específicas, usar esas
        if configuraciones_activas.exists():
            usuarios = [config.usuario for config in configuraciones_activas]
        else:
            # Usar reglas por defecto basadas en roles
            from django.contrib.auth.models import Group
            
            # Gerentes siempre reciben alertas
            gerentes = Group.objects.get(name='Gerente').user_set.all()
            usuarios.extend(gerentes)
            
            # Vendedor asignado recibe alertas de sus facturas
            if factura.vendedor:
                usuarios.append(factura.vendedor)
            
            # Distribuidor asignado recibe alertas de sus facturas
            if factura.distribuidor:
                usuarios.append(factura.distribuidor)
        
        return list(set(usuarios))  # Eliminar duplicados
    
    @classmethod
    def procesar_todas_las_alertas(cls):
        """Procesar todas las alertas automáticas"""
        resultados = {
            'vencimiento': cls.generar_alertas_vencimiento(),
            'montos_altos': cls.generar_alertas_montos_altos(),
            'sin_pagos': cls.generar_alertas_sin_pagos(),
        }
        
        total_generadas = sum(resultados.values())
        
        return {
            'total_generadas': total_generadas,
            'detalle': resultados
        }
    
    @classmethod
    def obtener_alertas_usuario(cls, usuario, solo_nuevas=False):
        """Obtener alertas para un usuario específico"""
        queryset = Alerta.objects.filter(usuario_destinatario=usuario)
        
        if solo_nuevas:
            queryset = queryset.filter(estado='nueva')
        
        return queryset.select_related('tipo_alerta', 'factura', 'factura__cliente').order_by('-fecha_generacion')
    
    @classmethod
    def marcar_alertas_como_leidas(cls, usuario, alertas_ids=None):
        """Marcar alertas específicas o todas como leídas para un usuario"""
        queryset = Alerta.objects.filter(
            usuario_destinatario=usuario,
            estado='nueva'
        )
        
        if alertas_ids:
            queryset = queryset.filter(id__in=alertas_ids)
        
        alertas_actualizadas = queryset.update(
            estado='leida',
            fecha_leida=timezone.now()
        )
        
        return alertas_actualizadas