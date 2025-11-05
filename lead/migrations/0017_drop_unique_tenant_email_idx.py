from django.db import migrations, connection


class Migration(migrations.Migration):

    dependencies = [
        ('lead', '0016_drop_unique_email_on_leads'),
    ]

    def _drop_unique_email_indexes(apps, schema_editor):
        with connection.cursor() as cursor:
            # Find all UNIQUE indexes that include `email_address`
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
            index_names = [row[0] for row in cursor.fetchall()]
            for index_name in index_names:
                try:
                    cursor.execute(f"ALTER TABLE `leads` DROP INDEX `{index_name}`")
                except Exception:
                    # Ignore if already dropped or not applicable on this DB
                    pass

    operations = [
        migrations.RunPython(_drop_unique_email_indexes, reverse_code=migrations.RunPython.noop),
    ]


