from django.db import migrations, connection


def ensure_non_unique_indexes_and_drop_unique_email(apps, schema_editor):
    with connection.cursor() as cursor:
        # Create separate non-unique indexes if they don't exist
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_leads_tenant_id ON leads (tenant_id)")
        except Exception:
            pass
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_leads_email_address ON leads (email_address)")
        except Exception:
            pass

        # Find and drop ALL UNIQUE indexes that include email_address
        cursor.execute(
            """
            SELECT DISTINCT INDEX_NAME
            FROM information_schema.statistics
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'leads'
              AND COLUMN_NAME = 'email_address'
              AND NON_UNIQUE = 0
            """
        )
        for (index_name,) in cursor.fetchall():
            try:
                cursor.execute(f"ALTER TABLE leads DROP INDEX {index_name}")
            except Exception:
                # Ignore if already dropped or locked by FK; previous CREATE INDEX should satisfy FK
                try:
                    cursor.execute(f"ALTER TABLE leads DROP INDEX `{index_name}`")
                except Exception:
                    pass


class Migration(migrations.Migration):

    dependencies = [
        ("lead", "0017_drop_unique_tenant_email_idx"),
    ]

    operations = [
        migrations.RunPython(ensure_non_unique_indexes_and_drop_unique_email, reverse_code=migrations.RunPython.noop),
    ]


