from django.utils import timezone
from django.db import models
from datetime import timedelta

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
        # Si no existe un TipoAlerta de vencimiento activo, crear uno por defecto
        if not tipos_vencimiento.exists():
            TipoAlerta.objects.create(
                nombre='Vencimiento de Factura',
                tipo='vencimiento',
                activa=True,
            )
            tipos_vencimiento = TipoAlerta.objects.filter(tipo='vencimiento', activa=True)
        
        alertas_generadas = 0
        
        for tipo_alerta in tipos_vencimiento:
            # Simplificación: limitar anticipación a 5 días independientemente de configuración
            dias_anticipacion = 5
            fecha_limite = timezone.now().date() + timedelta(days=dias_anticipacion)
            
            # Buscar facturas que vencen en el período especificado O que ya están vencidas
            facturas_por_vencer = Factura.objects.filter(
                models.Q(
                    # Facturas por vencer en el período (hoy .. +dias_anticipacion)
                    fecha_vencimiento__lte=fecha_limite,
                    fecha_vencimiento__gte=timezone.now().date()
                ) | models.Q(
                    # Facturas ya vencidas (críticas), independientemente de si el estado ya fue actualizado
                    fecha_vencimiento__lt=timezone.now().date()
                ),
                estado__in=['pendiente', 'parcial', 'vencida']
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
                        subtipo = 'vencida'
                        mensaje = f"La factura {factura.numero_factura} del cliente {factura.cliente.nombre} venció hace {abs(dias_restantes)} días. Saldo pendiente: ${factura.saldo_pendiente}"
                    else:
                        titulo = f"Por vencer: Factura {factura.numero_factura}"
                        prioridad = 'alta' if dias_restantes <= 3 else 'media'
                        subtipo = 'por_vencer'
                        mensaje = f"La factura {factura.numero_factura} del cliente {factura.cliente.nombre} vence en {dias_restantes} días. Saldo pendiente: ${factura.saldo_pendiente}"
                    
                    alerta = Alerta.objects.create(
                        tipo_alerta=tipo_alerta,
                        factura=factura,
                        usuario_destinatario=usuario,
                        titulo=titulo,
                        mensaje=mensaje,
                        subtipo=subtipo,
                        prioridad=prioridad,
                        datos_contexto={
                            'dias_restantes': dias_restantes,
                            'saldo_pendiente': str(factura.saldo_pendiente),
                            'cliente_id': getattr(factura, 'cliente_id', None),
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
            try:
                from django.contrib.auth.models import Group
                # Gerentes siempre reciben alertas (si el grupo existe)
                grupo_gerente = Group.objects.get(name='Gerente')
                gerentes = grupo_gerente.user_set.all()
                usuarios.extend(gerentes)
            except Exception:
                # Si el grupo no existe, continuamos sin agregar gerentes
                pass

            # Vendedor asignado recibe alertas de sus facturas
            if getattr(factura, 'vendedor', None):
                usuarios.append(factura.vendedor)

        # Simplificación: excluir distribuidores de los destinatarios
        try:
            from django.contrib.auth.models import Group
            distribuidores = set(Group.objects.get(name='Distribuidor').user_set.values_list('id', flat=True))
            usuarios = [u for u in usuarios if u.id not in distribuidores]
        except Exception:  # pragma: no cover - si el grupo no existe o cualquier otro error, no filtramos
            pass
        
        return list(set(usuarios))  # Eliminar duplicados
    
    @classmethod
    def generar_alerta_factura_especifica(cls, factura, tipo='vencimiento'):
        """Generar alerta de vencimiento para una factura específica (único soporte)."""
        from .models import TipoAlerta

        tipo_alerta = TipoAlerta.objects.filter(tipo='vencimiento', activa=True).first()
        if not tipo_alerta:
            tipo_alerta = TipoAlerta.objects.create(
                nombre='Vencimiento de Factura',
                tipo='vencimiento',
                activa=True,
            )

        usuarios_destinatarios = cls._obtener_usuarios_destinatarios(factura, tipo_alerta)

        hoy = timezone.now().date()
        alertas_creadas = 0
        for usuario in usuarios_destinatarios:
            # Evitar duplicados activos
            existe = Alerta.objects.filter(
                factura=factura,
                usuario_destinatario=usuario,
                tipo_alerta=tipo_alerta,
                estado__in=['nueva', 'leida']
            ).exists()
            if existe:
                continue

            dias_restantes = (factura.fecha_vencimiento - hoy).days
            if dias_restantes <= 0:
                dias = (hoy - factura.fecha_vencimiento).days
                titulo = f"VENCIDA: Factura {factura.numero_factura}"
                prioridad = 'critica'
                subtipo = 'vencida'
                mensaje = (
                    f"La factura {factura.numero_factura} del cliente {factura.cliente.nombre} "
                    f"está vencida desde {factura.fecha_vencimiento} (hace {abs(dias)} días). "
                    f"Saldo pendiente: ${factura.saldo_pendiente}"
                )
            else:
                titulo = f"Por vencer: Factura {factura.numero_factura}"
                prioridad = 'alta' if dias_restantes <= 3 else 'media'
                subtipo = 'por_vencer'
                mensaje = (
                    f"La factura {factura.numero_factura} del cliente {factura.cliente.nombre} "
                    f"vence en {dias_restantes} días. Saldo pendiente: ${factura.saldo_pendiente}"
                )

            Alerta.objects.create(
                tipo_alerta=tipo_alerta,
                factura=factura,
                usuario_destinatario=usuario,
                titulo=titulo,
                mensaje=mensaje,
                subtipo=subtipo,
                prioridad=prioridad,
                datos_contexto={
                    'cliente_id': getattr(factura, 'cliente_id', None),
                    'cliente_nombre': getattr(factura.cliente, 'nombre', None),
                    'fecha_vencimiento': str(factura.fecha_vencimiento),
                    'valor_total': str(factura.valor_total),
                    'saldo_pendiente': str(factura.saldo_pendiente),
                    'estado_factura': factura.estado,
                    'dias_restantes': (factura.fecha_vencimiento - hoy).days,
                }
            )
            alertas_creadas += 1

        return alertas_creadas > 0
    
    @classmethod
    def procesar_todas_las_alertas(cls):
        """Procesar todas las alertas automáticas"""
        # Simplificación: solo generar alertas de vencimiento
        resultados = {
            'vencimiento': cls.generar_alertas_vencimiento(),
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
        """Deprecated: método sin efecto (compatibilidad)."""
        return 0

    @classmethod
    def cambiar_estado_alerta(cls, usuario, alerta_id, leida=True):
        """Actualizar el estado (leída/no leída) de una alerta específica"""
        try:
            alerta = Alerta.objects.get(id=alerta_id, usuario_destinatario=usuario)
        except Alerta.DoesNotExist:
            return None

        if leida:
            if alerta.estado != 'leida':
                alerta.estado = 'leida'
                alerta.fecha_leida = timezone.now()
                alerta.save(update_fields=['estado', 'fecha_leida'])
        else:
            if alerta.estado != 'nueva':
                alerta.estado = 'nueva'
                alerta.fecha_leida = None
                alerta.save(update_fields=['estado', 'fecha_leida'])

        return alerta

    @classmethod
    def cambiar_estado_multiple(cls, usuario, alertas_ids, leida=True):
        """Deprecated: método sin efecto (compatibilidad)."""
        return 0

    @classmethod
    def obtener_alertas_recientes(cls, usuario, desde=None, limite=20):
        """Retorna alertas nuevas o recientes para un usuario"""
        queryset = Alerta.objects.filter(usuario_destinatario=usuario)

        if desde:
            queryset = queryset.filter(fecha_generacion__gt=desde)

        return queryset.select_related('tipo_alerta', 'factura').order_by('-fecha_generacion')[:limite]

    @classmethod
    def estadisticas_por_dia(cls, dias=7):
        """Calcula cantidad de alertas por día para últimos 'dias'"""
        fecha_inicio = timezone.now().date() - timedelta(days=dias - 1)
        queryset = Alerta.objects.filter(fecha_generacion__date__gte=fecha_inicio)

        resultados = (
            queryset
            .extra({'dia': "date(fecha_generacion)"})
            .values('dia')
            .order_by('dia')
            .annotate(total=models.Count('id'), leidas=models.Count('id', filter=models.Q(estado='leida')))
        )

        return [
            {
                'fecha': registro['dia'],
                'total': registro['total'],
                'leidas': registro['leidas']
            }
            for registro in resultados
        ]

    @classmethod
    def tiempo_promedio_lectura(cls):
        """Calcula tiempo promedio entre generación y lectura en horas"""
        alertas_con_lectura = Alerta.objects.filter(
            fecha_leida__isnull=False,
            fecha_generacion__isnull=False
        )

        if not alertas_con_lectura.exists():
            return None

        total_segundos = 0
        contador = 0

        for alerta in alertas_con_lectura:
            if alerta.fecha_generacion and alerta.fecha_leida:
                total_segundos += (alerta.fecha_leida - alerta.fecha_generacion).total_seconds()
                contador += 1

        if contador == 0:
            return None

        promedio_horas = total_segundos / contador / 3600
        return round(promedio_horas, 2)