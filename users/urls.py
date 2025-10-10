from django.urls import path
from .views import (
    CustomUserListView,
    CustomUserRetrieveUpdateDestroyView,
    AssignRoleView,
    RemoveRoleView,
    UserProfileView,
    current_user_view,
    logout_view
)
from .auth import (
    CustomUserLoginView,
    CustomUserRegisterView,
    ChangePasswordView
)

urlpatterns = [
    # Autenticación
    path('auth/register/', CustomUserRegisterView.as_view(), name='register'),
    path('auth/login/', CustomUserLoginView.as_view(), name='login'),
    path('auth/logout/', logout_view, name='logout'),
    path('auth/user/', current_user_view, name='current-user'),
    path('auth/profile/', UserProfileView.as_view(), name='user-profile'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='change-password'),

    # Gestión de usuarios (solo para gerentes)
    path('users/', CustomUserListView.as_view(), name='user-list'),
    path('users/<int:pk>/', CustomUserRetrieveUpdateDestroyView.as_view(), name='user-detail'),
    path('users/<int:pk>/assign-role/', AssignRoleView.as_view(), name='assign-role'),
    path('users/<int:pk>/remove-role/', RemoveRoleView.as_view(), name='remove-role'),
]
