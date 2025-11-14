# Generated manually to ensure role_id column exists

from django.db import migrations, connection


def ensure_role_id_column(apps, schema_editor):
    """
    Ensure role_id column exists in employees table
    """
    with connection.cursor() as cursor:
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
                # Add role_id column
                try:
                    # First add the column
                    cursor.execute("ALTER TABLE `employees` ADD COLUMN `role_id` BIGINT NULL")
                    print("✓ Added role_id column to employees table")
                    
                    # Then add foreign key constraint
                    try:
                        cursor.execute("""
                            ALTER TABLE `employees` 
                            ADD CONSTRAINT `employees_role_id_fk` 
                            FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) 
                            ON DELETE SET NULL
                        """)
                        print("✓ Added foreign key constraint for role_id")
                    except Exception as fk_error:
                        # Check if constraint already exists with different name
                        print(f"Warning: Could not add foreign key constraint: {fk_error}")
                        print("Column role_id was added but foreign key constraint may need manual setup")
                except Exception as e:
                    print(f"✗ Error adding role_id: {e}")
            else:
                print("✗ Warning: roles table does not exist. Please run role app migrations first.")
        else:
            print("✓ role_id column already exists in employees table")


class Migration(migrations.Migration):

    dependencies = [
        ('role', '0001_initial'),
        ('employee', '0010_remove_account_type_temp'),
    ]

    operations = [
        migrations.RunPython(
            ensure_role_id_column,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

