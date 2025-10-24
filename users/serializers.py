from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from .models import CustomUser


class CustomUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    roles = serializers.SerializerMethodField(read_only=True)
    # Aceptar campos de frontend
    username = serializers.CharField(required=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    # Booleans de rol provenientes del front (solo escritura)
    is_gerente = serializers.BooleanField(write_only=True, required=False, default=False)
    is_vendedor = serializers.BooleanField(write_only=True, required=False, default=False)
    is_distribuidor = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = CustomUser
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "name",
            "password",
            "is_active",
            # entrada de rol
            "is_gerente",
            "is_vendedor",
            "is_distribuidor",
            # salida
            "roles",
        )
        extra_kwargs = {"password": {"write_only": True}}

    def validate(self, attrs):
        # Validar que exactamente un rol esté seleccionado
        g = attrs.get("is_gerente", False)
        v = attrs.get("is_vendedor", False)
        d = attrs.get("is_distribuidor", False)
        selected = sum([1 if g else 0, 1 if v else 0, 1 if d else 0])
        if selected != 1 and self.instance is None:
            # En creación exigimos un solo rol
            raise serializers.ValidationError({"roles": "Debe seleccionar exactamente un rol"})

        # No permitir que un usuario se desactive a sí mismo
        request = self.context.get('request') if hasattr(self, 'context') else None
        if self.instance is not None and request is not None:
            if 'is_active' in attrs and attrs.get('is_active') is False:
                if getattr(request.user, 'pk', None) == getattr(self.instance, 'pk', None):
                    raise serializers.ValidationError({
                        'is_active': 'No puede desactivarse a sí mismo.'
                    })
        return attrs

    def _apply_role_groups(self, user, is_gerente, is_vendedor, is_distribuidor):
        # Limpia y asigna un único grupo basado en booleans
        user.groups.clear()
        role_map = {
            True: "Gerente",
            False: None,
        }
        group_name = None
        if is_gerente:
            group_name = "Gerente"
        elif is_vendedor:
            group_name = "Vendedor"
        elif is_distribuidor:
            group_name = "Distribuidor"
        if group_name:
            try:
                group = Group.objects.get(name=group_name)
                user.groups.add(group)
            except Group.DoesNotExist:
                pass

    def create(self, validated_data):
        # Extraer booleans de rol
        is_gerente = validated_data.pop("is_gerente", False)
        is_vendedor = validated_data.pop("is_vendedor", False)
        is_distribuidor = validated_data.pop("is_distribuidor", False)

        # Hash de contraseña
        raw_password = validated_data.get("password")
        if raw_password:
            validated_data["password"] = make_password(raw_password)

        # Completar name si viene vacío
        if not validated_data.get("name"):
            fn = validated_data.get("first_name", "").strip()
            ln = validated_data.get("last_name", "").strip()
            full = (fn + " " + ln).strip()
            if full:
                validated_data["name"] = full

        user = super().create(validated_data)
        # Asignar grupo según booleans
        self._apply_role_groups(user, is_gerente, is_vendedor, is_distribuidor)
        user.save()
        return user

    def update(self, instance, validated_data):
        # Permitir actualizar roles si vienen
        is_gerente = validated_data.pop("is_gerente", None)
        is_vendedor = validated_data.pop("is_vendedor", None)
        is_distribuidor = validated_data.pop("is_distribuidor", None)

        if "password" in validated_data:
            validated_data["password"] = make_password(validated_data["password"])

        # Completar name si no viene y hay cambios de nombres
        if not validated_data.get("name"):
            fn = validated_data.get("first_name", instance.first_name).strip() if instance.first_name is not None else validated_data.get("first_name", "").strip()
            ln = validated_data.get("last_name", instance.last_name).strip() if instance.last_name is not None else validated_data.get("last_name", "").strip()
            full = (fn + " " + ln).strip()
            if full:
                validated_data.setdefault("name", full)

        user = super().update(instance, validated_data)

        # Si llegaron flags de rol (al menos uno no es None), actualizamos grupos
        if any(x is not None for x in [is_gerente, is_vendedor, is_distribuidor]):
            self._apply_role_groups(
                user,
                bool(is_gerente),
                bool(is_vendedor),
                bool(is_distribuidor),
            )
            user.save()

        return user

    def get_roles(self, obj):
        return list(obj.groups.values_list("name", flat=True))

class CustomUserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value

class AssignRoleSerializer(serializers.Serializer):
    role = serializers.CharField(write_only=True)

    def validate_role(self, value):
        if not Group.objects.filter(name=value).exists():
            raise serializers.ValidationError(f"El rol '{value}' no existe")
        return value

    def update(self, instance, validated_data):
        rolename = validated_data.get("role")
        instance.groups.clear()
        group = Group.objects.get(name=rolename)
        instance.groups.add(group)
        instance.save()
        return instance

class RemoveRoleSerializer(serializers.Serializer):
    role = serializers.CharField()

    def update(self, instance, validated_data):
        rolename = validated_data.get("role")
        group = instance.groups.filter(name=rolename).first()
        if group:
            instance.groups.remove(group)
        return instance

class UserBasicSerializer(serializers.ModelSerializer):
    """Serializer básico para mostrar información de usuario en relaciones"""
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    roles = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomUser
        fields = ('id', 'name', 'email', 'full_name', 'roles')
    
    def get_roles(self, obj):
        return list(obj.groups.values_list("name", flat=True))
