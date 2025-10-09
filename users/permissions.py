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
    groupname = 'Distribuidor'  # Actualizado para consistencia

class IsDistribuidor(IsInGroup):
    groupname = 'Distribuidor'

# Alias para compatibilidad
class IsAdministrador(IsGerente):
    """Alias para IsGerente - mantiene compatibilidad"""
    pass

class IsAdministradorOrVendedor(BasePermission):
    """Permite acceso a Gerentes (Administradores) y Vendedores"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        return request.user.groups.filter(
            name__in=['Gerente', 'Vendedor']
        ).exists()

class IsGerenteOrVendedor(IsAdministradorOrVendedor):
    """Alias para IsAdministradorOrVendedor"""
    pass

class IsGerenteOrVendedorOrDistribuidor(BasePermission):
    """Permite acceso a Gerentes, Vendedores y Distribuidores"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        return request.user.groups.filter(
            name__in=['Gerente', 'Vendedor', 'Distribuidor']
        ).exists()
