from django.contrib import admin
from .models import Role, Permission, RolePermission


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'display_name', 'description']


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ['module', 'action', 'display_name']
    list_filter = ['module', 'action']
    search_fields = ['module', 'action', 'display_name']


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ['role', 'permission', 'created_at']
    list_filter = ['role', 'permission', 'created_at']
    search_fields = ['role__name', 'permission__module', 'permission__action']

