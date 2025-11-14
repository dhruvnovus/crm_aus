"""
Serializers for Role and Permission management
"""
from rest_framework import serializers
from .models import Role, Permission, RolePermission


class PermissionSerializer(serializers.ModelSerializer):
    """Serializer for Permission model"""
    module_display = serializers.CharField(source='get_module_display', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = Permission
        fields = ['id', 'module', 'module_display', 'action', 'action_display', 'display_name']
        read_only_fields = ['id']


class RolePermissionSerializer(serializers.ModelSerializer):
    """Serializer for RolePermission relationship"""
    permission = PermissionSerializer(read_only=True)
    permission_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = RolePermission
        fields = ['id', 'permission', 'permission_id', 'created_at']
        read_only_fields = ['id', 'created_at']


class RoleSerializer(serializers.ModelSerializer):
    """Serializer for Role model"""
    name_display = serializers.CharField(source='get_name_display', read_only=True)
    permissions = PermissionSerializer(many=True, read_only=True, source='role_permissions.permission')
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of permission IDs to assign to this role"
    )
    
    class Meta:
        model = Role
        fields = ['id', 'name', 'name_display', 'display_name', 'description', 'is_active', 
                  'permissions', 'permission_ids', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        permission_ids = validated_data.pop('permission_ids', [])
        role = Role.objects.create(**validated_data)
        
        # Assign permissions
        if permission_ids:
            permissions = Permission.objects.filter(id__in=permission_ids)
            for perm in permissions:
                RolePermission.objects.get_or_create(role=role, permission=perm)
        
        return role
    
    def update(self, instance, validated_data):
        permission_ids = validated_data.pop('permission_ids', None)
        
        # Update role fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update permissions if provided
        if permission_ids is not None:
            # Remove existing permissions
            RolePermission.objects.filter(role=instance).delete()
            # Add new permissions
            permissions = Permission.objects.filter(id__in=permission_ids)
            for perm in permissions:
                RolePermission.objects.get_or_create(role=instance, permission=perm)
        
        return instance


class RolePermissionConfigSerializer(serializers.Serializer):
    """Serializer for configuring role permissions in bulk"""
    role_id = serializers.IntegerField()
    module = serializers.ChoiceField(choices=Permission.MODULE_CHOICES)
    permissions = serializers.ListField(
        child=serializers.ChoiceField(choices=Permission.ACTION_CHOICES),
        help_text="List of actions to allow (e.g., ['create', 'read', 'update', 'delete'])"
    )

