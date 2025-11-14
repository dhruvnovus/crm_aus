"""
Custom permission classes for role-based access control
"""
from rest_framework import permissions
from employee.models import Employee


class HasModulePermission(permissions.BasePermission):
    """
    Permission class that checks if user has permission for a specific module and action.
    Usage: permission_classes = [HasModulePermission(module='customers', action='create')]
    """
    
    def __init__(self, module=None, action=None):
        self.module = module
        self.action = action
    
    def has_permission(self, request, view):
        """
        Check if the user has permission for the module and action.
        """
        # Allow unauthenticated users to be handled by IsAuthenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get employee from request
        employee = self._get_employee(request)
        if not employee:
            return False
        
        # Map view actions to permission actions
        action_map = {
            'list': 'read',
            'retrieve': 'read',
            'create': 'create',
            'update': 'update',
            'partial_update': 'update',
            'destroy': 'delete',
        }
        
        # Get action from view or use default
        view_action = getattr(view, 'action', None)
        permission_action = action_map.get(view_action, 'read')
        
        # Use provided action or fallback to permission_action
        action = self.action or permission_action
        
        # Use provided module or get from view
        module = self.module or getattr(view, 'permission_module', None)
        
        if not module:
            # Try to infer from view name
            view_name = view.__class__.__name__.lower()
            if 'customer' in view_name:
                module = 'customers'
            elif 'lead' in view_name:
                module = 'leads'
            elif 'task' in view_name:
                module = 'tasks'
            elif 'mail' in view_name:
                module = 'mail'
            elif 'employee' in view_name or 'user' in view_name:
                module = 'user_management'
            elif 'notification' in view_name:
                module = 'notifications'
            else:
                # Default: allow if super admin
                return employee.account_type == 'super_admin'
        
        return employee.has_permission(module, action)
    
    def _get_employee(self, request):
        """
        Get Employee instance from request.user
        """
        user = request.user
        
        # If user is already an Employee instance
        if isinstance(user, Employee):
            return user
        
        # Try to get Employee by email (since User.username is email)
        if hasattr(user, 'email'):
            return Employee.objects.filter(email=user.email, is_active=True).first()
        elif hasattr(user, 'username'):
            return Employee.objects.filter(email=user.username, is_active=True).first()
        
        return None


class IsSuperAdmin(permissions.BasePermission):
    """
    Permission class that only allows super admin users.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        employee = self._get_employee(request)
        if not employee:
            return False
        
        return employee.account_type == 'super_admin'
    
    def _get_employee(self, request):
        user = request.user
        if isinstance(user, Employee):
            return user
        if hasattr(user, 'email'):
            return Employee.objects.filter(email=user.email, is_active=True).first()
        elif hasattr(user, 'username'):
            return Employee.objects.filter(email=user.username, is_active=True).first()
        return None

