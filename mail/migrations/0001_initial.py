from django.db import migrations, models
import django.db.models.deletion
import mail.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('task', '0003_taskattachment_file_taskattachment_file_size_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Mail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('from_email', models.EmailField(blank=True, max_length=255, null=True)),
                ('to_emails', models.JSONField(default=list)),
                ('cc_emails', models.JSONField(blank=True, default=list)),
                ('bcc_emails', models.JSONField(blank=True, default=list)),
                ('subject', models.CharField(max_length=255)),
                ('body', models.TextField()),
                ('direction', models.CharField(choices=[('inbound', 'Inbound'), ('outbound', 'Outbound')], default='outbound', max_length=10)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('sent', 'Sent'), ('scheduled', 'Scheduled')], default='draft', max_length=10)),
                ('scheduled_at', models.DateTimeField(blank=True, null=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('linked_task', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='emails', to='task.task')),
            ],
            options={'db_table': 'mail_messages', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='MailAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(blank=True, null=True, upload_to=mail.models.mail_attachment_upload_path)),
                ('filename', models.CharField(max_length=255)),
                ('content_type', models.CharField(blank=True, max_length=100, null=True)),
                ('file_size', models.PositiveIntegerField(blank=True, null=True)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('mail', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='mail.mail')),
            ],
            options={'db_table': 'mail_attachments', 'ordering': ['-uploaded_at']},
        ),
    ]

