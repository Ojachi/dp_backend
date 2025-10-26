from rest_framework import serializers
from .models import Alerta, TipoAlerta, ConfiguracionAlerta

class TipoAlertaSerializer(serializers.ModelSerializer):
    """Serializer para tipos de alertas"""
    class Meta:
        model = TipoAlerta
        fields = '__all__'
        read_only_fields = ['creado', 'actualizado']

class AlertaListSerializer(serializers.ModelSerializer):
    """Serializer para listar alertas"""
    tipo_alerta_nombre = serializers.CharField(source='tipo_alerta.nombre', read_only=True)
    tipo = serializers.CharField(source='tipo_alerta.tipo', read_only=True)
    factura_numero = serializers.CharField(source='factura.numero_factura', read_only=True)
    cliente_nombre = serializers.CharField(source='factura.cliente.nombre', read_only=True)
    
    class Meta:
        model = Alerta
        fields = [
            'id', 'titulo', 'mensaje', 'subtipo', 'prioridad', 'estado',
            'tipo', 'tipo_alerta_nombre', 'factura_numero', 'cliente_nombre',
            'fecha_generacion', 'fecha_leida', 'fecha_procesada'
        ]

class AlertaDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado para alertas"""
    tipo_alerta = TipoAlertaSerializer(read_only=True)
    factura_info = serializers.SerializerMethodField()
    usuario_procesado_nombre = serializers.CharField(source='usuario_procesado.get_full_name', read_only=True)
    
    class Meta:
        model = Alerta
        fields = [
            'id', 'tipo_alerta', 'factura', 'factura_info', 'titulo', 'mensaje', 'subtipo',
            'prioridad', 'estado', 'datos_contexto',
            'fecha_generacion', 'fecha_leida', 'fecha_procesada',
            'usuario_procesado', 'usuario_procesado_nombre'
        ]
        read_only_fields = [
            'tipo_alerta', 'factura', 'usuario_destinatario', 
            'fecha_generacion', 'fecha_leida', 'fecha_procesada'
        ]
    
    def get_factura_info(self, obj):
        return {
            'id': obj.factura.pk,
            'numero_factura': obj.factura.numero_factura,
            'cliente_nombre': obj.factura.cliente.nombre,
            'valor_total': obj.factura.valor_total,
            'saldo_pendiente': obj.factura.saldo_pendiente,
            'estado': obj.factura.estado,
            'fecha_vencimiento': obj.factura.fecha_vencimiento
        }

class AlertaUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizar estado de alertas"""
    class Meta:
        model = Alerta
        fields = ['estado']
        
    def validate_estado(self, value):
        """Validar transiciones de estado permitidas"""
        if self.instance:
            estado_actual = self.instance.estado
            
            # Definir transiciones permitidas
            transiciones_permitidas = {
                'nueva': ['leida', 'procesada', 'descartada'],
                'leida': ['procesada', 'descartada'],
                'procesada': [],  # Estado final
                'descartada': []  # Estado final
            }
            
            if value not in transiciones_permitidas.get(estado_actual, []):
                raise serializers.ValidationError(
                    f"No se puede cambiar de '{estado_actual}' a '{value}'"
                )
        
        return value

class ConfiguracionAlertaSerializer(serializers.ModelSerializer):
    """Serializer para configuración de alertas por usuario"""
    tipo_alerta_info = serializers.SerializerMethodField()
    
    class Meta:
        model = ConfiguracionAlerta
        fields = [
            'id', 'tipo_alerta', 'tipo_alerta_info',
            'recibir_notificacion', 'activa'
        ]
        read_only_fields = ['usuario']
    
    def get_tipo_alerta_info(self, obj):
        return {
            'id': obj.tipo_alerta.id,
            'nombre': obj.tipo_alerta.nombre,
            'tipo': obj.tipo_alerta.tipo,
            # descripcion removida del modelo
        }

class EstadisticasAlertasSerializer(serializers.Serializer):
    """Serializer para estadísticas de alertas"""
    total_alertas = serializers.IntegerField()
    alertas_nuevas = serializers.IntegerField()
    alertas_criticas = serializers.IntegerField()
    alertas_recientes = serializers.IntegerField()
    alertas_por_tipo = serializers.DictField()
    alertas_por_prioridad = serializers.DictField()
    alertas_por_dia = serializers.ListField(child=serializers.DictField(), required=False)
    tiempo_promedio_lectura = serializers.FloatField(allow_null=True)
 