# Generated manually to remove leftover account_type_temp field and ensure role_id exists

from django.db import migrations, connection, models
import django.db.models.deletion


def remove_account_type_temp_and_ensure_role_id(apps, schema_editor):
    """
    Remove account_type_temp field if it exists and ensure role_id column exists
    """
    with connection.cursor() as cursor:
        # Check if account_type_temp column exists and remove it
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'employees'
              AND COLUMN_NAME = 'account_type_temp'
        """)
        temp_exists = cursor.fetchone()[0] > 0
        
        if temp_exists:
            # Drop the column
            try:
                cursor.execute("ALTER TABLE `employees` DROP COLUMN `account_type_temp`")
                print("Removed account_type_temp column from employees table")
            except Exception as e:
                print(f"Error removing account_type_temp: {e}")
        
        # Check if role_id column exists
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'employees'
              AND COLUMN_NAME = 'role_id'
        """)
        role_id_exists = cursor.fetchone()[0] > 0
        
        if not role_id_exists:
            # Check if roles table exists
            cursor.execute("""
                SELECT COUNT(*)
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'roles'
            """)
            roles_table_exists = cursor.fetchone()[0] > 0
            
            if roles_table_exists:
                # Add role_id column with foreign key constraint
                try:
                    # First add the column
                    cursor.execute("ALTER TABLE `employees` ADD COLUMN `role_id` BIGINT NULL")
                    print("Added role_id column to employees table")
                    
                    # Then add foreign key constraint
                    try:
                        cursor.execute("""
                            ALTER TABLE `employees` 
                            ADD CONSTRAINT `employees_role_id_fk` 
                            FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) 
                            ON DELETE SET NULL
                        """)
                        print("Added foreign key constraint for role_id")
                    except Exception as fk_error:
                        print(f"Warning: Could not add foreign key constraint: {fk_error}")
                        print("Column role_id was added but without foreign key constraint")
                except Exception as e:
                    print(f"Error adding role_id: {e}")
            else:
                print("Warning: roles table does not exist. Please run role app migrations first.")
        else:
            print("role_id column already exists in employees table")


class Migration(migrations.Migration):

    dependencies = [
        ('role', '0001_initial'),
        ('employee', '0009_employee_role'),
    ]

    operations = [
        migrations.RunPython(
            remove_account_type_temp_and_ensure_role_id,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

