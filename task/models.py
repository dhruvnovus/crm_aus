from django.db import models
from django.utils import timezone
from employee.models import Employee


class Task(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    STATUS_CHOICES = [
        ('to_do', 'To Do'),
        ('in_progress', 'In Progress'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    assigned_to = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks'
    )
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='to_do')
    due_date = models.DateField()
    due_time = models.TimeField()

    # Soft delete and timestamps
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tasks'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        if self.status == 'completed':
            return False
        due_dt = timezone.make_aware(
            timezone.datetime.combine(self.due_date, self.due_time)
        ) if timezone.is_naive(timezone.now()) else timezone.datetime.combine(self.due_date, self.due_time)
        return timezone.now() > due_dt


class Subtask(models.Model):
    parent_task = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name='subtasks', null=True, blank=True
    )
    child_task = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name='as_subtask_of', null=True, blank=True
    )
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'task_subtasks'
        ordering = ['sort_order', 'id']
        unique_together = ('parent_task', 'child_task')

    def __str__(self):
        return f"Subtask(parent={self.parent_task_id}, child={self.child_task_id})"


class TaskAttachment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='attachments')
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True, null=True)
    data_base64 = models.TextField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'task_attachments'
        ordering = ['-uploaded_at']


class TaskReminder(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='reminders')
    remind_at = models.DateTimeField()
    is_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'task_reminders'
        ordering = ['remind_at']


class TaskHistory(models.Model):
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('assign', 'Assign'),
        ('status_change', 'Status Change'),
        ('comment', 'Comment'),
        ('attachment_add', 'Attachment Added'),
        ('attachment_remove', 'Attachment Removed'),
        ('reminder_set', 'Reminder Set'),
        ('delete', 'Delete'),
    ]

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='history_entries')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    changed_by = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='task_history_changes'
    )
    changes = models.JSONField(default=dict, blank=True)
    note = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'task_history'
        ordering = ['-timestamp']

    def __str__(self):
        return f"TaskHistory(task_id={self.task_id}, action={self.action}, at={self.timestamp})"


