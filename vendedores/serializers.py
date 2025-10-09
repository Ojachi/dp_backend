from rest_framework import serializers
from .models import Vendedor
from users.serializers import UserBasicSerializer

class VendedorListSerializer(serializers.ModelSerializer):
    """Serializer para listar vendedores"""
    usuario_nombre = serializers.CharField(source='usuario.get_full_name', read_only=True)
    usuario_email = serializers.CharField(source='usuario.email', read_only=True)
    facturas_asignadas = serializers.SerializerMethodField()
    
    class Meta:
        model = Vendedor
        fields = [
            'id', 'codigo', 'zona', 'usuario', 'usuario_nombre', 
            'usuario_email', 'facturas_asignadas', 'creado'
        ]
    
    def get_facturas_asignadas(self, obj):
        return obj.usuario.facturas_vendedor.count()

class VendedorDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado para vendedor"""
    usuario = UserBasicSerializer(read_only=True)
    facturas_asignadas = serializers.SerializerMethodField()
    facturas_pendientes = serializers.SerializerMethodField()
    total_cartera = serializers.SerializerMethodField()
    
    class Meta:
        model = Vendedor
        fields = [
            'id', 'codigo', 'zona', 'usuario', 'facturas_asignadas',
            'facturas_pendientes', 'total_cartera', 'creado', 'actualizado'
        ]
    
    def get_facturas_asignadas(self, obj):
        return obj.usuario.facturas_vendedor.count()
    
    def get_facturas_pendientes(self, obj):
        return obj.usuario.facturas_vendedor.filter(
            estado__in=['pendiente', 'parcial']
        ).count()
    
    def get_total_cartera(self, obj):
        from django.db.models import Sum
        total = obj.usuario.facturas_vendedor.filter(
            estado__in=['pendiente', 'parcial']
        ).aggregate(total=Sum('saldo_pendiente'))['total']
        return total or 0

class VendedorCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer para crear/actualizar vendedores"""
    usuario_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Vendedor
        fields = ['codigo', 'zona', 'usuario_id']
    
    def validate_codigo(self, value):
        """Validar código único"""
        if self.instance and self.instance.codigo == value:
            return value
        if Vendedor.objects.filter(codigo=value).exists():
            raise serializers.ValidationError("Ya existe un vendedor con este código")
        return value
    
    def validate_usuario_id(self, value):
        """Validar que el usuario existe y no esté asignado"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            usuario = User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("El usuario especificado no existe")
        
        # Verificar que no esté ya asignado como vendedor
        if self.instance and self.instance.usuario.id == value:
            return value
            
        if Vendedor.objects.filter(usuario_id=value).exists():
            raise serializers.ValidationError("Este usuario ya está asignado como vendedor")
        
        return value
