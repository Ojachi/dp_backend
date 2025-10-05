from django.apps import apps
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Group, Permission

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
        'Repartidor': [
            'view_factura'
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
