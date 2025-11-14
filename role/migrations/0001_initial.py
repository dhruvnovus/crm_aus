# Generated manually for role app

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Permission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('module', models.CharField(choices=[('customers', 'Customers'), ('leads', 'Leads'), ('tasks', 'Tasks'), ('task_history', 'Task History'), ('mail', 'Mail'), ('employee', 'Employee'), ('reports', 'Reports'), ('settings', 'Settings'), ('notifications', 'Notifications')], help_text='Module name', max_length=50)),
                ('action', models.CharField(choices=[('create', 'Create'), ('read', 'Read'), ('update', 'Update'), ('delete', 'Delete')], help_text='Action type', max_length=20)),
                ('display_name', models.CharField(help_text='Display name for the permission', max_length=100)),
            ],
            options={
                'verbose_name': 'Permission',
                'verbose_name_plural': 'Permissions',
                'db_table': 'permissions',
                'ordering': ['module', 'action'],
            },
        ),
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(choices=[('super_admin', 'Super Admin'), ('sales_staff', 'Sales Staff')], help_text='Role name', max_length=50, unique=True)),
                ('display_name', models.CharField(help_text='Display name for the role', max_length=100)),
                ('description', models.TextField(blank=True, help_text='Description of the role', null=True)),
                ('is_active', models.BooleanField(default=True, help_text='Whether this role is active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Role',
                'verbose_name_plural': 'Roles',
                'db_table': 'roles',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='RolePermission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='role_permissions', to='role.permission')),
                ('role', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='role_permissions', to='role.role')),
            ],
            options={
                'verbose_name': 'Role Permission',
                'verbose_name_plural': 'Role Permissions',
                'db_table': 'role_permissions',
            },
        ),
        migrations.AddConstraint(
            model_name='permission',
            constraint=models.UniqueConstraint(fields=('module', 'action'), name='role_permission_module_action_unique'),
        ),
        migrations.AddConstraint(
            model_name='rolepermission',
            constraint=models.UniqueConstraint(fields=('role', 'permission'), name='role_rolepermission_role_permission_unique'),
        ),
    ]

