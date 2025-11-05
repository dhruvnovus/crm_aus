from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('lead', '0015_alter_lead_options'),
    ]

    def _drop_indexes_if_exist(apps, schema_editor):
        """Drop legacy unique indexes if present (MySQL/MariaDB safe)."""
        index_names = [
            'leads_tenant_id_email_address_14df65d6_uniq',
            'email_address',
            'email_address_uniq',
        ]
        with schema_editor.connection.cursor() as cursor:
            for idx in index_names:
                cursor.execute(
                    """
                    SELECT COUNT(1)
                    FROM information_schema.statistics
                    WHERE table_schema = DATABASE()
                      AND table_name = 'leads'
                      AND index_name = %s
                    """,
                    [idx],
                )
                exists = cursor.fetchone()[0] > 0
                if exists:
                    cursor.execute(f"DROP INDEX `{idx}` ON `leads`")

    operations = [
        migrations.RunPython(_drop_indexes_if_exist, reverse_code=migrations.RunPython.noop),
    ]


