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
    permission_classes = [IsAuthenticated]
    pagination_class = None  # Disable pagination
    filterset_fields = ['module', 'action']
    ordering_fields = ['module', 'action']
    
    def list(self, request, *args, **kwargs):
        # Get all permissions
        permissions = self.get_queryset()
        
        # Get module display names
        module_display_map = dict(Permission.MODULE_CHOICES)
        
        # Get all unique modules from permissions
        all_modules = set(perm.module for perm in permissions)
        
        # Get roles (super_admin and sales_staff)
        roles = Role.objects.filter(name__in=['super_admin', 'sales_staff']).prefetch_related('role_permissions__permission')
        
        # Build response structure: role -> module -> permissions
        response_data = {}
        
        for role in roles:
            role_name = role.name
            response_data[role_name] = {}
            
            # Initialize all modules for this role with False permissions
            for module in all_modules:
                module_display = module_display_map.get(module, module.title())
                response_data[role_name][module_display] = {
                    'can_create': False,
                    'can_read': False,
                    'can_update': False,
                    'can_delete': False
                }
            
            # Set permissions for this role based on role_permissions
            for role_perm in role.role_permissions.all():
                perm = role_perm.permission
                module = perm.module
                module_display = module_display_map.get(module, module.title())
                action = perm.action
                
                # Set the appropriate flag based on action
                if action == 'create':
                    response_data[role_name][module_display]['can_create'] = True
                elif action == 'read':
                    response_data[role_name][module_display]['can_read'] = True
                elif action == 'update':
                    response_data[role_name][module_display]['can_update'] = True
                elif action == 'delete':
                    response_data[role_name][module_display]['can_delete'] = True
        
        # Ensure both roles exist even if they don't have permissions
        for role_name in ['super_admin', 'sales_staff']:
            if role_name not in response_data:
                response_data[role_name] = {}
                for module in all_modules:
                    module_display = module_display_map.get(module, module.title())
                    response_data[role_name][module_display] = {
                        'can_create': False,
                        'can_read': False,
                        'can_update': False,
                        'can_delete': False
                    }
        
        return Response(response_data, status=status.HTTP_200_OK)

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
        description="Get all permissions for an employee. If employee_id is provided, returns that employee's permissions (any authenticated user can view any employee's permissions). Otherwise returns current user's permissions.",
        tags=["Roles & Permissions"],
        parameters=[
            OpenApiParameter(
                name='employee_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Employee ID to get permissions for. If not provided, returns current user\'s permissions.'
            ),
        ],
        responses={200: PermissionSerializer(many=True)},
    )
    @action(detail=False, methods=['get'], url_path='my-permissions', permission_classes=[IsAuthenticated])
    def my_permissions(self, request):
        """
        Get all permissions for an employee.
        - If employee_id is provided: Returns that employee's permissions (any authenticated user can view any employee's permissions)
        - If employee_id is not provided: Returns current authenticated user's permissions
        """
        # Check if employee_id is provided in query params
        employee_id = request.query_params.get('employee_id')
        
        if employee_id:
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