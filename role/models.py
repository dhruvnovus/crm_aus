from django.db import models


class Role(models.Model):
    """
    Role model for role-based access control
    """
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('sales_staff', 'Sales Staff'),
    ]
    
    name = models.CharField(
        max_length=50,
        unique=True,
        choices=ROLE_CHOICES,
        help_text="Role name"
    )
    display_name = models.CharField(
        max_length=100,
        help_text="Display name for the role"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Description of the role"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this role is active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'roles'
        ordering = ['name']
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
    
    def __str__(self):
        return self.display_name


class Permission(models.Model):
    """
    Permission model for module-level permissions
    """
    MODULE_CHOICES = [
        ('customers', 'Customers'),
        ('leads', 'Leads'),
        ('tasks', 'Tasks'),
        ('task_history', 'Task History'),
        ('mail', 'Mail'),
        ('employee', 'Employee'),
        ('reports', 'Reports'),
        ('settings', 'Settings'),
        ('notifications', 'Notifications'),
    ]
    
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('read', 'Read'),
        ('update', 'Update'),
        ('delete', 'Delete'),
    ]
    
    module = models.CharField(
        max_length=50,
        choices=MODULE_CHOICES,
        help_text="Module name"
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        help_text="Action type"
    )
    display_name = models.CharField(
        max_length=100,
        help_text="Display name for the permission"
    )
    
    class Meta:
        db_table = 'permissions'
        unique_together = ('module', 'action')
        ordering = ['module', 'action']
        verbose_name = 'Permission'
        verbose_name_plural = 'Permissions'
    
    def __str__(self):
        return f"{self.get_module_display()} - {self.get_action_display()}"


class RolePermission(models.Model):
    """
    Many-to-many relationship between Role and Permission
    """
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='role_permissions'
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name='role_permissions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'role_permissions'
        unique_together = ('role', 'permission')
        verbose_name = 'Role Permission'
        verbose_name_plural = 'Role Permissions'
    
    def __str__(self):
        return f"{self.role.display_name} - {self.permission}"