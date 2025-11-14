from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from django.utils.crypto import get_random_string
import uuid


class Employee(models.Model):
    """
    Employee model for CRM system with account types: Super Admin and Sales Staff
    """
    
    # Account Type Choices
    ACCOUNT_TYPE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('sales_staff', 'Sales Staff'),
    ]
    
    # Staff Type Choices
    STAFF_TYPE_CHOICES = [
        ('employee', 'Employee'),
        ('contractor', 'Contractor'),
    ]
    
    # Title Choices
    TITLE_CHOICES = [
        ('mr', 'Mr'),
        ('mrs', 'Mrs'),
        ('miss', 'Miss'),
        ('ms', 'Ms'),
        ('other', 'Other'),
    ]
    
    # Gender Choices
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]
    
    # Account Information
    account_type = models.CharField(
        max_length=20,
        choices=ACCOUNT_TYPE_CHOICES,
        null=True,
        blank=True,
        help_text="Account type: Super Admin or Sales Staff"
    )
    role = models.ForeignKey(
        'role.Role',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
        help_text="Role assigned to this employee"
    )
    staff_type = models.CharField(
        max_length=20,
        choices=STAFF_TYPE_CHOICES,
        default='employee',
        help_text="Staff type: Employee or Contractor"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Enable if employee is currently active"
    )
    is_resigned = models.BooleanField(
        default=False,
        help_text="Mark if employee has resigned"
    )
    
    # Personal Information
    title = models.CharField(
        max_length=10,
        choices=TITLE_CHOICES,
        default='mr',
        help_text="Title: Mr, Mrs, Miss, Ms, Other"
    )
    first_name = models.CharField(
        max_length=100,
        help_text="Employee's first name"
    )
    last_name = models.CharField(
        max_length=100,
        help_text="Employee's last name"
    )
    email = models.EmailField(
        unique=True,
        help_text="Employee's email address"
    )
    password = models.CharField(
        max_length=128,
        help_text="Employee's password (will be hashed)"
    )
    position = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Employee's position/title"
    )
    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES,
        default='male',
        help_text="Employee's gender"
    )
    
    # Contact & Location
    date_of_birth = models.DateField(
        blank=True,
        null=True,
        help_text="Employee's date of birth"
    )
    mobile_no = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
        )],
        help_text="Employee's mobile number"
    )
    landline_no = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
        )],
        help_text="Employee's landline number"
    )
    language_spoken = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Languages spoken by employee"
    )
    unit_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Unit/Apartment number"
    )
    address = models.TextField(
        blank=True,
        null=True,
        help_text="Employee's full address"
    )
    post_code = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        help_text="Postal code"
    )
    
    # Profile & Notes
    profile_image = models.TextField(
        blank=True,
        null=True,
        help_text="Employee's profile image as Base64 string"
    )
    admin_notes = models.TextField(
        blank=True,
        null=True,
        help_text="Internal notes visible only to administrators"
    )
    
    # Contracted Hours
    hours_per_week = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Weekly contracted hours"
    )
    
    is_deleted = models.BooleanField(
        default=False,
        help_text="Is deleted"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'employees'
        ordering = ['-created_at']
        verbose_name = 'Employee'
        verbose_name_plural = 'Employees'
    
    def __str__(self):
        return f"{self.get_title_display()} {self.first_name} {self.last_name}"
    
    @property
    def full_name(self):
        """Return the full name of the employee"""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def display_name(self):
        """Return the display name with title"""
        return f"{self.get_title_display()} {self.full_name}"
    
    @property
    def status_display(self):
        """Return the current status of the employee"""
        if self.is_resigned:
            return "Resigned"
        elif self.is_active:
            return "Active"
        else:
            return "Inactive"
    
    @property
    def is_authenticated(self):
        """Always return True for authenticated Employee instances"""
        return True
    
    @property
    def is_anonymous(self):
        """Always return False for Employee instances"""
        return False
    
    @property
    def username(self):
        """Return email as username for compatibility with DRF"""
        return self.email
    
    def set_password(self, raw_password):
        """Set the password for the employee"""
        self.password = make_password(raw_password)
        self.save()
    
    def check_password(self, raw_password):
        """Check if the provided password matches the employee's password"""
        return check_password(raw_password, self.password)
    
    def authenticate(self, email, password):
        """Authenticate an employee with email and password"""
        try:
            employee = Employee.objects.get(email=email, is_active=True)
            if employee.check_password(password):
                return employee
        except Employee.DoesNotExist:
            pass
        return None
    
    def has_permission(self, module, action):
        """
        Check if employee has permission for a module and action.
        Super admins have all permissions.
        """
        # Super admins have all permissions
        if self.account_type == 'super_admin':
            return True
        
        # Check role permissions
        if self.role and self.role.is_active:
            from role.models import RolePermission
            return RolePermission.objects.filter(
                role=self.role,
                permission__module=module,
                permission__action=action
            ).exists()
        
        return False
    
    def get_permissions(self):
        """
        Get all permissions for this employee as a list of dicts.
        Super admins get all permissions.
        """
        from role.models import Permission, RolePermission
        
        # Get module display names
        module_display_map = dict(Permission.MODULE_CHOICES)
        
        # Get all permissions (flat list)
        if self.account_type == 'super_admin':
            permissions_list = [
                {'module': module, 'action': action}
                for module, _ in Permission.MODULE_CHOICES
                for action, _ in Permission.ACTION_CHOICES
            ]
        else:
            # Get permissions from role
            if not self.role or not self.role.is_active:
                return []
            
            permissions_list = [
                {'module': rp.permission.module, 'action': rp.permission.action}
                for rp in RolePermission.objects.filter(role=self.role).select_related('permission')
            ]
        
        # Group permissions by module
        permissions_by_module = {}
        for perm in permissions_list:
            module = perm['module']
            action = perm['action']
            
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
        return list(permissions_by_module.values())


class EmergencyContact(models.Model):
    """
    Emergency contact information for employees
    """
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='emergency_contacts',
        help_text="Employee this contact belongs to"
    )
    name = models.CharField(
        max_length=100,
        help_text="Emergency contact's name"
    )
    relationship = models.CharField(
        max_length=50,
        help_text="Relationship to employee (e.g., Spouse, Parent, Sibling)"
    )
    phone = models.CharField(
        max_length=20,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
        )],
        help_text="Emergency contact's phone number"
    )
    email = models.EmailField(
        blank=True,
        null=True,
        help_text="Emergency contact's email address"
    )
    address = models.TextField(
        blank=True,
        null=True,
        help_text="Emergency contact's address"
    )
    
    is_deleted = models.BooleanField(
        default=False,
        help_text="Is deleted"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'emergency_contacts'
        ordering = ['-created_at']
        verbose_name = 'Emergency Contact'
        verbose_name_plural = 'Emergency Contacts'
    
    def __str__(self):
        return f"{self.name} ({self.relationship}) - {self.employee.full_name}"


class EmployeeHistory(models.Model):
    """
    Audit history for Employee changes
    """
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('read', 'Read'),
    ]

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='history_entries',
        help_text='Employee this history entry pertains to'
    )
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='employee_history_changes',
        help_text='User who performed the change (if available)'
    )
    changes = models.JSONField(
        default=dict,
        blank=True,
        help_text='Dictionary of field changes {field: {from: value, to: value}}'
    )
    is_deleted = models.BooleanField(
        default=False,
        help_text="Is deleted"
    )
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'employee_history'
        ordering = ['-timestamp']
        verbose_name = 'Employee History'
        verbose_name_plural = 'Employee History'

    def __str__(self):
        return f"EmployeeHistory(employee_id={self.employee_id}, action={self.action}, at={self.timestamp})"


class PasswordResetToken(models.Model):
    """
    Model to store password reset tokens for employees
    """
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens',
        help_text="Employee requesting password reset"
    )
    token = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique token for password reset"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(help_text="Token expiration time")
    is_used = models.BooleanField(
        default=False,
        help_text="Whether this token has been used"
    )
    
    class Meta:
        db_table = 'password_reset_tokens'
        ordering = ['-created_at']
        verbose_name = 'Password Reset Token'
        verbose_name_plural = 'Password Reset Tokens'
    
    def __str__(self):
        return f"PasswordResetToken(employee={self.employee.email}, created={self.created_at})"
    
    def is_expired(self):
        """Check if the token has expired"""
        return timezone.now() > self.expires_at
    
    def is_valid(self):
        """Check if the token is valid (not used and not expired)"""
        return not self.is_used and not self.is_expired()
    
    @classmethod
    def create_token(cls, employee):
        """Create a new password reset token for an employee"""
        # Delete any existing unused tokens for this employee
        cls.objects.filter(employee=employee, is_used=False).delete()
        
        # Create new token
        token = get_random_string(50)
        expires_at = timezone.now() + timezone.timedelta(hours=1)  # 1 hour expiry
        
        return cls.objects.create(
            employee=employee,
            token=token,
            expires_at=expires_at
        )
