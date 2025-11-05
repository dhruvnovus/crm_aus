"""
Notification models for user notifications
"""
from django.db import models
from django.utils import timezone
from employee.models import Employee


class Notification(models.Model):
    """
    Notification model for user notifications including lead assignments, task assignments, and reminders
    """
    TYPE_CHOICES = [
        ('lead_assignment', 'Lead Assignment'),
        ('task_assignment', 'Task Assignment'),
        ('task_reminder', 'Task Reminder'),
    ]

    user = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='notifications',
        help_text='User who will receive this notification'
    )
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Related object references (using GenericForeignKey alternative)
    lead_id = models.PositiveIntegerField(null=True, blank=True, help_text='Related lead ID if notification type is lead_assignment')
    task_id = models.PositiveIntegerField(null=True, blank=True, help_text='Related task ID if notification type is task_assignment or task_reminder')
    reminder_id = models.PositiveIntegerField(null=True, blank=True, help_text='Related reminder ID if notification type is task_reminder')
    
    # Additional metadata
    metadata = models.JSONField(default=dict, blank=True, help_text='Additional notification data')
    
    # Read status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'notification_type']),
        ]

    def __str__(self):
        return f"Notification for {self.user} - {self.notification_type} - {self.title}"

    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

