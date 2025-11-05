from django.db import migrations, connection


def drop_all_email_address_indexes(apps, schema_editor):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT DISTINCT INDEX_NAME
            FROM information_schema.statistics
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'leads'
              AND COLUMN_NAME = 'email_address'
            """
        )
        for (index_name,) in cursor.fetchall():
            # Try without quotes then with backticks for compatibility
            for stmt in [
                f"ALTER TABLE leads DROP INDEX {index_name}",
                f"ALTER TABLE `leads` DROP INDEX `{index_name}`",
            ]:
                try:
                    cursor.execute(stmt)
                    break
                except Exception:
                    continue


class Migration(migrations.Migration):

    dependencies = [
        ("lead", "0018_drop_remaining_email_unique_and_add_indexes"),
    ]

    operations = [
        migrations.RunPython(drop_all_email_address_indexes, reverse_code=migrations.RunPython.noop),
    ]


