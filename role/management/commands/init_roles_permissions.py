"""
Management command to initialize default roles and permissions
Usage: python manage.py init_roles_permissions
"""
from django.core.management.base import BaseCommand
from role.models import Role, Permission, RolePermission


class Command(BaseCommand):
    help = 'Initialize default roles and permissions for the CRM system'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== Initializing Roles and Permissions ===\n'))
        
        # Create all permissions
        self.stdout.write('Creating permissions...')
        permissions_created = 0
        for module, module_display in Permission.MODULE_CHOICES:
            for action, action_display in Permission.ACTION_CHOICES:
                perm, created = Permission.objects.get_or_create(
                    module=module,
                    action=action,
                    defaults={
                        'display_name': f'{module_display} - {action_display}'
                    }
                )
                if created:
                    permissions_created += 1
                    self.stdout.write(f'  ✓ Created: {perm.display_name}')
        
        self.stdout.write(self.style.SUCCESS(f'\nCreated {permissions_created} new permissions\n'))
        
        # Create default roles
        roles_config = [
            {
                'name': 'super_admin',
                'display_name': 'Super Admin',
                'description': 'Super admin role with full access to all modules and features',
                'permissions': 'all'  # All permissions
            },
            {
                'name': 'sales_staff',
                'display_name': 'Sales Staff',
                'description': 'Sales staff with access to core sales modules',
                'permissions': ['customers', 'leads', 'tasks', 'task_history', 'mail', 'notifications']
            },
        ]
        
        self.stdout.write('Creating roles...')
        for role_config in roles_config:
            role, created = Role.objects.get_or_create(
                name=role_config['name'],
                defaults={
                    'display_name': role_config['display_name'],
                    'description': role_config['description'],
                    'is_active': True
                }
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created role: {role.display_name}'))
            else:
                self.stdout.write(f'  - Role already exists: {role.display_name}')
            
            # Assign permissions
            if role_config['permissions'] == 'all':
                # Admin gets all permissions
                all_permissions = Permission.objects.all()
                for perm in all_permissions:
                    RolePermission.objects.get_or_create(role=role, permission=perm)
                self.stdout.write(f'    → Assigned all permissions ({all_permissions.count()} permissions)')
            else:
                # Other roles get specific module permissions
                assigned_count = 0
                for module in role_config['permissions']:
                    # Sales staff get full CRUD for their modules
                    module_perms = Permission.objects.filter(module=module)
                    
                    for perm in module_perms:
                        RolePermission.objects.get_or_create(role=role, permission=perm)
                        assigned_count += 1
                
                self.stdout.write(f'    → Assigned {assigned_count} permissions')
        
        self.stdout.write(self.style.SUCCESS('\n=== Roles and Permissions Initialized Successfully ===\n'))
        
        # Summary
        self.stdout.write('Summary:')
        self.stdout.write(f'  Roles: {Role.objects.count()}')
        self.stdout.write(f'  Permissions: {Permission.objects.count()}')
        self.stdout.write(f'  Role-Permission mappings: {RolePermission.objects.count()}\n')

