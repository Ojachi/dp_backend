from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from .models import CustomUser

class CustomUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    roles = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ("id", "name", "email", "password", "roles", "is_active")
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        validated_data["password"] = make_password(validated_data["password"])
        user = super().create(validated_data)
        # Asignar grupo por defecto (Vendedor)
        try:
            group = Group.objects.get(name="Vendedor")
            user.groups.add(group)
        except Group.DoesNotExist:
            pass
        return user

    def update(self, instance, validated_data):
        if "password" in validated_data:
            validated_data["password"] = make_password(validated_data["password"])
        return super().update(instance, validated_data)

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
