import os
from django.apps import apps
from django.db.models.signals import post_migrate, post_save, m2m_changed
from django.dispatch import receiver
from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model
from django.conf import settings

# Helpers para crear perfiles de roles automáticamente
def _generate_unique_code(model_cls, prefix: str, seed: int | None = None) -> str:
    """Genera un código único para Vendedor/Distribuidor.
    Formato por defecto: PREFIX-<seed> o PREFIX-<autoinc>.
    """
    base = f"{prefix}-{(seed or 0):05d}" if seed is not None else f"{prefix}-00000"
    code = base
    i = 1
    while model_cls.objects.filter(codigo=code).exists():
        code = f"{prefix}-{(seed or 0):05d}-{i}"
        i += 1
    return code

def ensure_role_profiles(user):
    """Crea perfiles Vendedor/Distribuidor cuando el usuario pertenece al grupo respectivo.
    No elimina perfiles al quitar grupos (idempotente al crear).
    """
    try:
        from vendedores.models import Vendedor
        from distribuidores.models import Distribuidor
    except Exception:
        return  # Durante migraciones iniciales puede no estar disponible

    # Vendedor
    if user.groups.filter(name='Vendedor').exists():
        if not hasattr(user, 'perfil_vendedor'):
            try:
                Vendedor.objects.create(
                    usuario=user,
                    codigo=_generate_unique_code(Vendedor, 'VEN', seed=user.id),
                    zona=''  # opcional
                )
            except Exception:
                pass

    # Distribuidor
    if user.groups.filter(name='Distribuidor').exists():
        if not hasattr(user, 'perfil_distribuidor'):
            try:
                Distribuidor.objects.create(
                    usuario=user,
                    codigo=_generate_unique_code(Distribuidor, 'DIS', seed=user.id),
                    zona=''  # opcional
                )
            except Exception:
                pass

@receiver(post_migrate)
def create_user_groups(sender, **kwargs):
    groups_permissions = {
        'Gerente': [
            'add_factura', 'change_factura', 'delete_factura', 'view_factura',
            'add_pago', 'change_pago', 'delete_pago', 'view_pago'
        ],
        'Vendedor': [
            'add_pago', 'change_pago', 'view_factura', 'view_pago'
        ],
        'Distribuidor': [
            'view_factura', 'add_pago', 'change_pago'
        ]
    }
    for group_name, perm_codenames in groups_permissions.items():
        group, created = Group.objects.get_or_create(name=group_name)
        for codename in perm_codenames:
            try:
                perm = Permission.objects.get(codename=codename)
                group.permissions.add(perm)
            except Permission.DoesNotExist:
                pass  # Si un permiso aún no existe, puedes loguear esto si quieres

    # Crear usuario base automáticamente al inicializar la BD (solo cuando corre migrations del app 'users')
    # Se crea únicamente si no existen usuarios todavía
    try:
        if getattr(sender, 'name', None) == 'users':
            User = get_user_model()
            if not User.objects.exists():
                email = os.environ.get('BASE_USER_EMAIL', 'admin@dp.local')
                password = os.environ.get('BASE_USER_PASSWORD', 'Admin123!')
                name = os.environ.get('BASE_USER_NAME', 'Administrador')

                user = User.objects.create_user(
                    email=email,
                    username=email.split('@')[0],
                    name=name,
                    is_active=True,
                    password=password,
                )
                # Asignar rol Gerente
                gerente, _ = Group.objects.get_or_create(name='Gerente')
                user.groups.add(gerente)
    except Exception:
        # En migrations iniciales puede fallar silenciosamente si aún no existe el modelo; se puede loguear si se requiere
        pass


# Crear perfiles al crear usuario
@receiver(post_save, sender=get_user_model())
def create_profiles_for_new_user(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        ensure_role_profiles(instance)
    except Exception:
        pass


# Crear perfiles cuando cambian los grupos del usuario (asignación de rol posterior)
@receiver(m2m_changed, sender=get_user_model().groups.through)
def create_profiles_on_group_assign(sender, instance, action, reverse, model, pk_set, **kwargs):
    if action in ('post_add',):
        try:
            ensure_role_profiles(instance)
        except Exception:
            pass
