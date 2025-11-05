"""
Utility functions for task reminder notifications.
"""

from task.models import TaskReminder


def mark_reminder_as_sent(reminder_id):
    """
    Mark a task reminder as sent.
    
    Args:
        reminder_id: The ID of the TaskReminder to mark as sent
        
    Returns:
        bool: True if reminder was marked as sent, False otherwise
    """
    try:
        reminder = TaskReminder.objects.get(id=reminder_id)
        reminder.is_sent = True
        reminder.save(update_fields=['is_sent'])
        return True
    except TaskReminder.DoesNotExist:
        return False
    except Exception as e:
        print(f"Error marking reminder as sent: {e}")
        return False

