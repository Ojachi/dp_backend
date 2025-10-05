from rest_framework.permissions import BasePermission

class IsInGroup(BasePermission):
    groupname = None

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        name = getattr(view, 'required_group', self.groupname)
        if not name:
            return False
        return request.user.groups.filter(name=name).exists()

class IsGerente(IsInGroup):
    groupname = 'Gerente'

class IsVendedor(IsInGroup):
    groupname = 'Vendedor'

class IsRepartidor(IsInGroup):
    groupname = 'Repartidor'
