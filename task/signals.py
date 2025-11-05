"""
Signals for creating notifications when task events occur
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Task


@receiver(post_save, sender=Task)
def create_task_assignment_notification(sender, instance, created, **kwargs):
    """
    Create notification when a task is assigned to a user
    Note: This handles new task assignments. Assignment changes are handled in views.
    """
    # Only create notification for new tasks with assigned user
    if created and instance.assigned_to:
        from notifications.signals import create_task_assignment_notification as create_notification
        create_notification(instance, is_new=True)

