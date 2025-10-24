from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = "Crea perfiles de Vendedor/Distribuidor para usuarios que pertenezcan al grupo y aún no tengan perfil."

    def handle(self, *args, **options):
        from users.signals import ensure_role_profiles
        User = get_user_model()
        created_vendedores = 0
        created_distribuidores = 0

        for user in User.objects.all():
            before_v = hasattr(user, 'perfil_vendedor')
            before_d = hasattr(user, 'perfil_distribuidor')
            ensure_role_profiles(user)
            after_v = hasattr(user, 'perfil_vendedor')
            after_d = hasattr(user, 'perfil_distribuidor')
            if (not before_v) and after_v:
                created_vendedores += 1
            if (not before_d) and after_d:
                created_distribuidores += 1

        self.stdout.write(self.style.SUCCESS(
            f"Perfiles creados: vendedores={created_vendedores}, distribuidores={created_distribuidores}"
        ))
