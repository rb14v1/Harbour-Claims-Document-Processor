from rest_framework import permissions


class IsAdjusterOrAdmin(permissions.BasePermission):
    """Only authenticated users with role adjuster or admin may use the API."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in ("adjuster", "admin"))


class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == "admin")
