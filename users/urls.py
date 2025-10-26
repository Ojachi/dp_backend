from django.urls import path
from .views import (
    CustomUserListView,
    CustomUserRetrieveUpdateDestroyView,
    ValidateEmailView,
    ValidateUsernameView,
    ResetUserPasswordView,
    current_user_view,
    logout_view
)
from .auth import (
    CustomUserLoginView,
)

urlpatterns = [
    # Autenticación
    path('auth/login/', CustomUserLoginView.as_view(), name='login'),
    path('auth/logout/', logout_view, name='logout'),
    path('auth/user/', current_user_view, name='current-user'),

    # Gestión de usuarios (solo para gerentes)
    path('users/', CustomUserListView.as_view(), name='user-list'),
    path('users/<int:pk>/', CustomUserRetrieveUpdateDestroyView.as_view(), name='user-detail'),
    path('users/validar-email/', ValidateEmailView.as_view(), name='validate-email'),
    path('users/validar-username/', ValidateUsernameView.as_view(), name='validate-username'),
    path('users/<int:pk>/reset-password/', ResetUserPasswordView.as_view(), name='reset-user-password'),
]
