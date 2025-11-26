from django.db import models
from django.utils import timezone
from task.models import Task
from employee.models import Employee


def mail_attachment_upload_path(instance, filename):
    return f'mail_attachments/mail_{instance.mail_id}/{filename}'


class Mail(models.Model):
    DIRECTION_CHOICES = [
        ('inbound', 'Inbound'),
        ('outbound', 'Outbound'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('scheduled', 'Scheduled'),
    ]
    TEMPLATE_CHOICES = [
        'dea_crm',
        'dea_crm_2',
    ]
    sender = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='mails')
    receivers = models.ManyToManyField(Employee, related_name='received_mails', blank=True)
    from_email = models.EmailField(max_length=255, blank=True, null=True)
    to_emails = models.JSONField(default=list)
    cc_emails = models.JSONField(default=list, blank=True)
    bcc_emails = models.JSONField(default=list, blank=True)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    templates = models.JSONField(
        default=list,
        blank=True,
        help_text="List of template keys to use when sending (e.g. ['dea_crm'])",
    )
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default='outbound')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    scheduled_at = models.DateTimeField(blank=True, null=True)
    linked_task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name='emails')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mail_messages'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.subject}"


class MailParticipantStatus(models.Model):
    """
    Track per-participant status for each mail (read/starred/delete status)
    Each employee who is a sender or receiver can have their own status
    - is_read: Whether the participant has read the mail
    - is_starred: Whether the participant has starred the mail
    - delete_status: Delete status ('sent'/'inbox' -> 'trash' -> 'deleted')
    """
    DELETE_CHOICES = [
        ('sent', 'Sent'),
        ('inbox', 'Inbox'),
        ('trash', 'Trash'),
        ('deleted', 'Deleted (softdelete)'),
    ]

    mail = models.ForeignKey(Mail, on_delete=models.CASCADE, related_name='participant_statuses')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='mail_statuses')
    is_read = models.BooleanField(default=False)
    is_starred = models.BooleanField(default=False)
    delete_status = models.CharField(max_length=10, choices=DELETE_CHOICES, default='inbox')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mail_participant_statuses'
        unique_together = [['mail', 'employee']]
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['mail', 'employee']),
            models.Index(fields=['employee', 'is_read']),
            models.Index(fields=['employee', 'is_starred']),
            models.Index(fields=['employee', 'delete_status']),
        ]

    def __str__(self):
        return f"Mail {self.mail_id} - Employee {self.employee_id} (delete_status={self.delete_status}, read={self.is_read}, starred={self.is_starred})"

class MailAttachment(models.Model):
    mail = models.ForeignKey(Mail, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to=mail_attachment_upload_path, blank=True, null=True)
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True, null=True)
    file_size = models.PositiveIntegerField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'mail_attachments'
        ordering = ['-uploaded_at']

    def save(self, *args, **kwargs):
        if self.file and not self.filename:
            self.filename = self.file.name
        if self.file and not self.content_type:
            import mimetypes
            self.content_type, _ = mimetypes.guess_type(self.file.name)
        if self.file and not self.file_size:
            try:
                self.file_size = self.file.size
            except (OSError, AttributeError):
                pass
        super().save(*args, **kwargs)

