from django.urls import path
from .views import (
    CustomUserListView,
    CustomUserRetrieveUpdateDestroyView,
    AssignRoleView,
    RemoveRoleView
)
from .auth import (
    CustomUserLoginView,
    CustomUserRegisterView,
    ChangePasswordView
)

urlpatterns = [
    path('users/register/', CustomUserRegisterView.as_view(), name='register'),
    path('users/login/', CustomUserLoginView.as_view(), name='login'),
    path('users/change-password/', ChangePasswordView.as_view(), name='change-password'),

    path('users/', CustomUserListView.as_view(), name='user-list'),
    path('users/<int:pk>/', CustomUserRetrieveUpdateDestroyView.as_view(), name='user-detail'),
    path('users/<int:pk>/assign-role/', AssignRoleView.as_view(), name='assign-role'),
    path('users/<int:pk>/remove-role/', RemoveRoleView.as_view(), name='remove-role'),
]
