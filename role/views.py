import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from employee.models import Employee
from .models import Role, Permission, RolePermission
from .serializers import (
    RoleSerializer,
    PermissionSerializer,
    RolePermissionConfigSerializer
)
from .permissions import IsSuperAdmin

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        summary="List all permissions",
        description="Get a list of all available permissions",
        tags=["Roles & Permissions"],
    ),
    retrieve=extend_schema(
        summary="Get permission details",
        description="Retrieve detailed information about a specific permission",
        tags=["Roles & Permissions"],
    ),
)
class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing permissions (read-only)
    """
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    pagination_class = None  # Disable pagination
    filterset_fields = ['module', 'action']
    ordering_fields = ['module', 'action']
    
    def list(self, request, *args, **kwargs):
        """
        Override list to return permissions grouped by module with boolean flags
        """
        # Get all permissions
        permissions = self.get_queryset()
        
        # Get module display names
        module_display_map = dict(Permission.MODULE_CHOICES)
        
        # Group permissions by module
        permissions_by_module = {}
        for perm in permissions:
            module = perm.module
            action = perm.action
            
            if module not in permissions_by_module:
                permissions_by_module[module] = {
                    'module': module_display_map.get(module, module.title()),
                    'can_create': False,
                    'can_read': False,
                    'can_update': False,
                    'can_delete': False
                }
            
            # Set the appropriate flag based on action
            if action == 'create':
                permissions_by_module[module]['can_create'] = True
            elif action == 'read':
                permissions_by_module[module]['can_read'] = True
            elif action == 'update':
                permissions_by_module[module]['can_update'] = True
            elif action == 'delete':
                permissions_by_module[module]['can_delete'] = True
        
        # Return as list
        return Response(list(permissions_by_module.values()), status=status.HTTP_200_OK)

@extend_schema_view(
    list=extend_schema(
        summary="List all roles",
        description="Get a list of all roles with their permissions",
        tags=["Roles & Permissions"],
    ),
    create=extend_schema(
        summary="Create role",
        description="Create a new role with permissions",
        tags=["Roles & Permissions"],
    ),
    retrieve=extend_schema(
        summary="Get role details",
        description="Retrieve detailed information about a specific role",
        tags=["Roles & Permissions"],
    ),
    update=extend_schema(
        summary="Update role (full)",
        description="Update all fields of a role including permissions",
        tags=["Roles & Permissions"],
    ),
    partial_update=extend_schema(
        summary="Update role (partial)",
        description="Update specific fields of a role",
        tags=["Roles & Permissions"],
    ),
    destroy=extend_schema(
        summary="Delete role",
        description="Delete a role from the system",
        tags=["Roles & Permissions"],
    ),
)
class RoleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing roles and their permissions
    """
    queryset = Role.objects.prefetch_related('role_permissions__permission').all().order_by('-created_at')
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    pagination_class = None  # Disable pagination
    filterset_fields = ['name', 'is_active']
    search_fields = ['name', 'display_name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['-created_at']  # Default ordering: newest first
    
    @extend_schema(
        summary="Configure role permissions",
        description="Configure permissions for a role in bulk",
        tags=["Roles & Permissions"],
        request=RolePermissionConfigSerializer(many=True),
        responses={200: RoleSerializer},
    )
    @action(detail=False, methods=['post'], url_path='configure-permissions')
    def configure_permissions(self, request):
        """
        Configure permissions for roles in bulk.
        Accepts a list of role permission configurations.
        """
        serializer = RolePermissionConfigSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        
        results = []
        for config in serializer.validated_data:
            role_id = config['role_id']
            module = config['module']
            actions = config['permissions']
            
            try:
                role = Role.objects.get(id=role_id)
                
                # Remove existing permissions for this module
                RolePermission.objects.filter(
                    role=role,
                    permission__module=module
                ).delete()
                
                # Add new permissions
                for action in actions:
                    permission = Permission.objects.get(module=module, action=action)
                    RolePermission.objects.get_or_create(role=role, permission=permission)
                
                results.append({
                    'role_id': role_id,
                    'module': module,
                    'status': 'success'
                })
            except (Role.DoesNotExist, Permission.DoesNotExist) as e:
                results.append({
                    'role_id': role_id,
                    'module': module,
                    'status': 'error',
                    'error': str(e)
                })
        
        return Response({'results': results}, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Get employee permissions",
        description="Get all permissions for an employee. If employee_id is provided, returns that employee's permissions (super admin only). Otherwise returns current user's permissions.",
        tags=["Roles & Permissions"],
        parameters=[
            OpenApiParameter(
                name='employee_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Employee ID to get permissions for (super admin only). If not provided, returns current user\'s permissions.'
            ),
        ],
        responses={200: PermissionSerializer(many=True)},
    )
    @action(detail=False, methods=['get'], url_path='my-permissions')
    def my_permissions(self, request):
        """
        Get all permissions for an employee.
        - If employee_id is provided: Returns that employee's permissions (super admin only)
        - If employee_id is not provided: Returns current authenticated user's permissions
        """
        # Check if employee_id is provided in query params
        employee_id = request.query_params.get('employee_id')
        
        if employee_id:
            # Get employee by ID - only super admins can query other employees
            user_email = getattr(request.user, 'email', None) or getattr(request.user, 'username', None)
            if not user_email:
                return Response(
                    {'detail': 'User email not found.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            current_employee = Employee.objects.filter(email=user_email, is_active=True).first()
            if not current_employee:
                return Response(
                    {'detail': 'Current employee not found.'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Only super admins can query other employees' permissions
            if current_employee.account_type != 'super_admin':
                return Response(
                    {'detail': 'Only super admins can view other employees\' permissions.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get the requested employee
            try:
                employee = Employee.objects.get(id=employee_id, is_active=True)
            except Employee.DoesNotExist:
                return Response(
                    {'detail': f'Employee with ID {employee_id} not found.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Get current authenticated user's employee
            user_email = getattr(request.user, 'email', None) or getattr(request.user, 'username', None)
            if not user_email:
                return Response(
                    {'detail': 'User email not found.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            employee = Employee.objects.filter(email=user_email, is_active=True).first()
            if not employee:
                return Response(
                    {'detail': 'Employee not found.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        permissions = employee.get_permissions()
        return Response({
            'employee_id': employee.id,
            'employee_name': employee.full_name,
            'role': {
                'id': employee.role.id if employee.role else None,
                'name': employee.role.name if employee.role else None,
                'display_name': employee.role.display_name if employee.role else None,
            } if employee.role else None,
            'permissions': permissions
        }, status=status.HTTP_200_OK)