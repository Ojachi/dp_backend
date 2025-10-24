from rest_framework import serializers
import re

from .models import Factura, FacturaImportacion
from vendedores.models import Vendedor
from distribuidores.models import Distribuidor
from clientes.serializers import ClienteListSerializer
from users.serializers import UserBasicSerializer
from clientes.models import Cliente, ClienteSucursal

class FacturaListSerializer(serializers.ModelSerializer):
    """Serializer para listar facturas con información básica"""
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    vendedor_nombre = serializers.SerializerMethodField()
    distribuidor_nombre = serializers.SerializerMethodField()
    total_pagado = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    saldo_pendiente = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    esta_vencida = serializers.BooleanField(read_only=True)
    dias_vencimiento = serializers.IntegerField(read_only=True)
    cliente_codigo = serializers.SerializerMethodField()
    condicion_pago = serializers.SerializerMethodField()

    class Meta:
        model = Factura
        fields = [
            'id', 'numero_factura', 'cliente', 'cliente_nombre',
            'vendedor', 'vendedor_nombre', 'distribuidor', 'distribuidor_nombre',
            'tipo',
            'fecha_emision', 'fecha_vencimiento', 'valor_total', 'estado', 'estado_entrega',
            'cliente_codigo', 'condicion_pago',
            'total_pagado', 'saldo_pendiente', 'esta_vencida', 'dias_vencimiento',
            'creado', 'actualizado'
        ]
        read_only_fields = ['creado', 'actualizado']

    def get_vendedor_nombre(self, obj):
        """Obtener nombre del vendedor manejando casos null"""
        if obj.vendedor:
            return obj.vendedor.get_full_name()
        # Fallback: si no está asignado en la factura, intentar desde la población de la sucursal
        suc = getattr(obj, 'cliente_sucursal', None)
        if suc and getattr(suc, 'poblacion', None) and getattr(suc.poblacion, 'vendedor', None):
            return suc.poblacion.vendedor.get_full_name()
        return None

    def get_distribuidor_nombre(self, obj):
        """Obtener nombre del distribuidor manejando casos null"""
        if obj.distribuidor:
            return obj.distribuidor.get_full_name()
        # Fallback: si no está asignado en la factura, intentar desde la población de la sucursal
        suc = getattr(obj, 'cliente_sucursal', None)
        if suc and getattr(suc, 'poblacion', None) and getattr(suc.poblacion, 'distribuidor', None):
            return suc.poblacion.distribuidor.get_full_name()
        return None

    def get_cliente_codigo(self, obj):
        suc = getattr(obj, 'cliente_sucursal', None)
        return suc.codigo if suc else None

    def get_condicion_pago(self, obj):
        suc = getattr(obj, 'cliente_sucursal', None)
        return suc.get_condicion_pago_display() if suc else None

class FacturaDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado para facturas con información completa"""
    cliente = ClienteListSerializer(read_only=True)
    vendedor = UserBasicSerializer(read_only=True)
    distribuidor = UserBasicSerializer(read_only=True)
    total_pagado = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    saldo_pendiente = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    esta_vencida = serializers.BooleanField(read_only=True)
    dias_vencimiento = serializers.IntegerField(read_only=True)
    cliente_codigo = serializers.SerializerMethodField()
    condicion_pago = serializers.SerializerMethodField()
    
    # IDs para asignación
    cliente_id = serializers.IntegerField(write_only=True)
    vendedor_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    distribuidor_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Factura
        fields = [
            'id', 'numero_factura', 'cliente', 'cliente_id',
            'vendedor', 'vendedor_id', 'distribuidor', 'distribuidor_id',
            'tipo',
            'fecha_emision', 'fecha_vencimiento', 'valor_total', 'estado', 'estado_entrega',
            'observaciones', 'total_pagado', 'saldo_pendiente', 
            'cliente_codigo', 'condicion_pago',
            'esta_vencida', 'dias_vencimiento', 'creado', 'actualizado'
        ]
        read_only_fields = ['creado', 'actualizado']

    def validate_numero_factura(self, value):
        """Normaliza y valida que el número de factura sea único.
        - El usuario puede ingresar solo dígitos (e.g. 001) o un valor con prefijo.
        - Siempre se almacena normalizado como "<TIPO>-<NNN>" (p. ej. FE-001).
        """
        # Obtener tipo desde el payload o desde la instancia
        data_inicial = getattr(self, 'initial_data', None)
        tipo = (data_inicial.get('tipo') if isinstance(data_inicial, dict) else None) or getattr(self.instance, 'tipo', None)
        if not tipo:
            # Si no hay tipo aún, devolver sin normalizar y dejar el error para la validación general
            return value
        digits = re.sub(r"\D", "", str(value or ""))
        if not digits:
            raise serializers.ValidationError("Ingrese solo dígitos para el número de factura")
        normalizado = f"{tipo}-{digits.zfill(3)}"
        # Si estamos editando y no cambió tras normalizar, permitir
        if self.instance and self.instance.numero_factura == normalizado:
            return normalizado
        if Factura.objects.filter(numero_factura=normalizado).exists():
            raise serializers.ValidationError("Ya existe una factura con este número")
        return normalizado

    def get_cliente_codigo(self, obj):
        suc = getattr(obj, 'cliente_sucursal', None)
        return suc.codigo if suc else None

    def get_condicion_pago(self, obj):
        suc = getattr(obj, 'cliente_sucursal', None)
        return suc.get_condicion_pago_display() if suc else None

    def validate(self, attrs):
        """Validaciones generales"""
        if attrs.get('fecha_vencimiento') and attrs.get('fecha_emision'):
            if attrs['fecha_vencimiento'] < attrs['fecha_emision']:
                raise serializers.ValidationError(
                    "La fecha de vencimiento no puede ser anterior a la fecha de emisión"
                )
        
        if attrs.get('valor_total') and attrs['valor_total'] <= 0:
            raise serializers.ValidationError(
                "El valor total debe ser mayor a cero"
            )
        
        return attrs

class FacturaCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear facturas"""
    cliente_id = serializers.IntegerField()
    vendedor_id = serializers.IntegerField(required=False, allow_null=True)
    distribuidor_id = serializers.IntegerField(required=False, allow_null=True)
    cliente_sucursal_id = serializers.IntegerField(required=False, allow_null=True)
    # Soporte para crear sucursal en la misma petición cuando no existe aún
    sucursal_poblacion_id = serializers.IntegerField(required=False, allow_null=True)
    sucursal_codigo = serializers.CharField(required=False, allow_blank=True)
    sucursal_condicion_pago = serializers.ChoiceField(
        required=False, allow_null=True,
        choices=[c[0] for c in ClienteSucursal.CONDICION_PAGO_CHOICES]
    )

    class Meta:
        model = Factura
        fields = [
            'numero_factura', 'cliente_id', 'cliente_sucursal_id', 'vendedor_id', 'distribuidor_id',
            'sucursal_poblacion_id', 'sucursal_codigo', 'sucursal_condicion_pago',
            'tipo',
            'fecha_emision', 'fecha_vencimiento', 'valor_total', 'observaciones'
        ]

    def validate_numero_factura(self, value):
        """Normaliza y valida que el número de factura sea único.
        - El usuario puede ingresar solo dígitos (e.g. 001) o un valor con prefijo.
        - Siempre se almacena normalizado como "<TIPO>-<NNN>" (p. ej. FE-001).
        """
        data_inicial = getattr(self, 'initial_data', None)
        tipo = data_inicial.get('tipo') if isinstance(data_inicial, dict) else None
        if not tipo:
            # Validación de tipo faltante se maneja en validate()
            return value
        digits = re.sub(r"\D", "", str(value or ""))
        if not digits:
            raise serializers.ValidationError("Ingrese solo dígitos para el número de factura")
        normalizado = f"{tipo}-{digits.zfill(3)}"
        if Factura.objects.filter(numero_factura=normalizado).exists():
            raise serializers.ValidationError("Ya existe una factura con este número")
        # Reemplazar el valor en data validada
        return normalizado

    def validate(self, attrs):
        """Validaciones generales"""
        # Mapear IDs de Vendedor/Distribuidor (modelos) a IDs de usuario para el modelo Factura.
        # También aceptar compatibilidad si se envía directamente el ID del usuario.
        vend_id = attrs.get('vendedor_id', None)
        if vend_id is not None:
            if Vendedor.objects.filter(pk=vend_id).exists():
                vendedor = Vendedor.objects.get(pk=vend_id)
                attrs['vendedor_id'] = vendedor.usuario.id
            elif Vendedor.objects.filter(usuario_id=vend_id).exists():
                # Ya es ID de usuario
                attrs['vendedor_id'] = vend_id
            else:
                raise serializers.ValidationError("El vendedor especificado no existe")

        dist_id = attrs.get('distribuidor_id', None)
        if dist_id is not None:
            if Distribuidor.objects.filter(pk=dist_id).exists():
                distrib = Distribuidor.objects.get(pk=dist_id)
                attrs['distribuidor_id'] = distrib.usuario.id
            elif Distribuidor.objects.filter(usuario_id=dist_id).exists():
                # Ya es ID de usuario
                attrs['distribuidor_id'] = dist_id
            else:
                raise serializers.ValidationError("El distribuidor especificado no existe")

        if attrs.get('fecha_vencimiento') and attrs.get('fecha_emision'):
            if attrs['fecha_vencimiento'] < attrs['fecha_emision']:
                raise serializers.ValidationError(
                    "La fecha de vencimiento no puede ser anterior a la fecha de emisión"
                )
        
        if attrs.get('valor_total') and attrs['valor_total'] <= 0:
            raise serializers.ValidationError(
                "El valor total debe ser mayor a cero"
            )

        # Validación de creación de sucursal inline
        sucursal_id = attrs.get('cliente_sucursal_id')
        pob_id = attrs.get('sucursal_poblacion_id')
        codigo = attrs.get('sucursal_codigo')
        cond = attrs.get('sucursal_condicion_pago')

        if sucursal_id is None and any(v is not None and v != '' for v in [pob_id, codigo, cond]):
            # Si se pretende crear sucursal inline, exigir campos mínimos
            missing = []
            if not pob_id:
                missing.append('sucursal_poblacion_id')
            if not codigo:
                missing.append('sucursal_codigo')
            # condicion de pago opcional: default en modelo es 'contado'
            if missing:
                raise serializers.ValidationError({
                    'sucursal': f"Faltan campos para crear la sucursal: {', '.join(missing)}"
                })
        
        return attrs
    
    def create(self, validated_data):
        """Crea la factura asignando vendedor/distribuidor desde la Población si aplica."""
        cliente_id = validated_data.pop('cliente_id')
        vendedor_id = validated_data.pop('vendedor_id', None)
        distribuidor_id = validated_data.pop('distribuidor_id', None)
        sucursal_id = validated_data.pop('cliente_sucursal_id', None)
        # Campos para posible creación inline de sucursal
        pob_id = validated_data.pop('sucursal_poblacion_id', None)
        suc_codigo = validated_data.pop('sucursal_codigo', None)
        suc_cond = validated_data.pop('sucursal_condicion_pago', None)
        sucursal = None
        cliente = Cliente.objects.get(pk=cliente_id)

        # Normalizar numero_factura si viene todavía sin prefijo (doble seguridad)
        numero_factura_val = validated_data.get('numero_factura')
        tipo = validated_data.get('tipo')
        if numero_factura_val and tipo and not re.match(rf"^{tipo}-", str(numero_factura_val)):
            digits = re.sub(r"\D", "", str(numero_factura_val))
            validated_data['numero_factura'] = f"{tipo}-{digits.zfill(3)}"

        # Si viene sucursal, validar que pertenezca al cliente y obtener población
        if sucursal_id is not None:
            try:
                sucursal = ClienteSucursal.objects.select_related('poblacion', 'cliente').get(pk=sucursal_id)
            except ClienteSucursal.DoesNotExist:
                raise serializers.ValidationError("La sucursal especificada no existe")
            if (sucursal.cliente.pk if sucursal.cliente else None) != cliente_id:
                raise serializers.ValidationError("La sucursal no pertenece al cliente indicado")
            poblacion = sucursal.poblacion
            # Autocompletar vendedor/distribuidor desde la población si no se enviaron
            if vendedor_id is None and poblacion and poblacion.vendedor:
                vendedor_id = poblacion.vendedor.id
            if distribuidor_id is None and poblacion and poblacion.distribuidor:
                distribuidor_id = poblacion.distribuidor.id
        else:
            # Intentar crear/obtener sucursal si se enviaron datos inline
            if pob_id and suc_codigo:
                try:
                    # Enforce global uniqueness de código de sucursal
                    existente = ClienteSucursal.objects.select_related('poblacion', 'cliente').filter(codigo=suc_codigo).first()
                    if existente:
                        # Si existe, validar que corresponda al mismo cliente y (opcional) misma población
                        if (existente.cliente.pk if existente.cliente else None) != cliente_id:
                            raise serializers.ValidationError({
                                'sucursal_codigo': 'Este código de sucursal ya está siendo usado por otro cliente.'
                            })
                        if pob_id and (existente.poblacion.pk if existente.poblacion else None) != int(pob_id):
                            raise serializers.ValidationError({
                                'sucursal_poblacion_id': 'El código de sucursal ya existe con otra población.'
                            })
                        sucursal = existente
                    else:
                        sucursal = ClienteSucursal.objects.create(
                            cliente=cliente,
                            poblacion_id=pob_id,
                            codigo=suc_codigo,
                            condicion_pago=suc_cond or 'contado'
                        )
                except serializers.ValidationError:
                    raise
                except Exception as exc:
                    raise serializers.ValidationError({
                        'sucursal': f'No fue posible crear/obtener la sucursal: {exc}'
                    })
                # Autocompletar vendedor/distribuidor desde la población si no se enviaron
                poblacion = sucursal.poblacion
                if vendedor_id is None and poblacion and poblacion.vendedor:
                    vendedor_id = poblacion.vendedor.id
                if distribuidor_id is None and poblacion and poblacion.distribuidor:
                    distribuidor_id = poblacion.distribuidor.id

        factura = Factura.objects.create(
            cliente=cliente,
            cliente_sucursal=sucursal,
            vendedor_id=vendedor_id,
            distribuidor_id=distribuidor_id,
            **validated_data
        )
        return factura

class FacturaUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizar facturas (solo ciertos campos)"""
    vendedor_id = serializers.IntegerField(required=False, allow_null=True)
    distribuidor_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Factura
        fields = [
            'vendedor_id', 'distribuidor_id', 'fecha_vencimiento', 
            'tipo',
            'observaciones', 'estado', 'estado_entrega'
        ]

    def validate_estado(self, value):
        """Validar cambios de estado"""
        if self.instance and value == 'pagada':
            if self.instance.saldo_pendiente > 0:
                raise serializers.ValidationError(
                    "No se puede marcar como pagada una factura con saldo pendiente"
                )
        return value

    def validate(self, attrs):
        # Validar permisos de actualización de estado_entrega según rol
        request = self.context.get('request')
        if request and 'estado_entrega' in attrs:
            user = request.user
            if not (user.groups.filter(name='Gerente').exists() or user.groups.filter(name='Distribuidor').exists()):
                raise serializers.ValidationError("Solo Gerente o Distribuidor pueden cambiar el estado de entrega")
        # Mapear IDs de Vendedor/Distribuidor (modelos) a IDs de usuario para el modelo Factura
        if 'vendedor_id' in attrs and attrs['vendedor_id'] is not None:
            vend_id = attrs['vendedor_id']
            if Vendedor.objects.filter(pk=vend_id).exists():
                vendedor = Vendedor.objects.get(pk=vend_id)
                attrs['vendedor_id'] = vendedor.usuario.id
            elif Vendedor.objects.filter(usuario_id=vend_id).exists():
                attrs['vendedor_id'] = vend_id
            else:
                raise serializers.ValidationError("El vendedor especificado no existe")

        if 'distribuidor_id' in attrs and attrs['distribuidor_id'] is not None:
            dist_id = attrs['distribuidor_id']
            if Distribuidor.objects.filter(pk=dist_id).exists():
                distrib = Distribuidor.objects.get(pk=dist_id)
                attrs['distribuidor_id'] = distrib.usuario.id
            elif Distribuidor.objects.filter(usuario_id=dist_id).exists():
                attrs['distribuidor_id'] = dist_id
            else:
                raise serializers.ValidationError("El distribuidor especificado no existe")

        return attrs

    def update(self, instance, validated_data):
        """Si cambia el tipo, mantener número normalizado coherente con el nuevo tipo."""
        tipo_nuevo = validated_data.get('tipo')
        if tipo_nuevo and tipo_nuevo != instance.tipo:
            # Extraer dígitos del número existente y recomponer con el nuevo tipo
            digits = re.sub(r"\D", "", str(instance.numero_factura or ""))
            if digits:
                nuevo_num = f"{tipo_nuevo}-{digits.zfill(3)}"
                # Verificar colisión
                if Factura.objects.filter(numero_factura=nuevo_num).exclude(pk=instance.pk).exists():
                    raise serializers.ValidationError({
                        'tipo': 'No se puede cambiar el tipo porque el número resultante ya existe.'
                    })
                instance.numero_factura = nuevo_num
        return super().update(instance, validated_data)


class FacturaImportacionSerializer(serializers.ModelSerializer):
    usuario = UserBasicSerializer(read_only=True)

    class Meta:
        model = FacturaImportacion
        fields = [
            'id',
            'archivo_nombre',
            'estado',
            'total_registros',
            'registros_validos',
            'registros_invalidos',
            'detalle',
            'errores',
            'usuario',
            'creado',
            'actualizado',
        ]
        read_only_fields = fields