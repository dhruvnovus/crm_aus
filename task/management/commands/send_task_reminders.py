"""
Management command to check for due task reminders and mark them as sent.

Run this command periodically (e.g., via cron) to check for reminders that need to be sent.
Example: python manage.py send_task_reminders
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from task.models import TaskReminder


class Command(BaseCommand):
    help = 'Check for due task reminders and mark them as sent'

    def handle(self, *args, **options):
        """Check for reminders due now and mark them"""
        now = timezone.now()
        
        # Find reminders that are due and not yet sent
        due_reminders = TaskReminder.objects.filter(
            remind_at__lte=now,
            is_sent=False
        ).select_related('task', 'task__assigned_to')
        
        if not due_reminders.exists():
            self.stdout.write(self.style.SUCCESS('No reminders due at this time.'))
            return
        
        processed_count = 0
        
        for reminder in due_reminders:
            try:
                task = reminder.task
                
                # Mark as sent if task is deleted or completed
                if task.is_deleted or task.status == 'completed':
                    reminder.is_sent = True
                    reminder.save(update_fields=['is_sent'])
                    processed_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Marked reminder {reminder.id} as sent (task {task.id} is {"deleted" if task.is_deleted else "completed"})'
                        )
                    )
                    continue
                
                # Mark as sent if no assigned user
                if not task.assigned_to:
                    reminder.is_sent = True
                    reminder.save(update_fields=['is_sent'])
                    processed_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Marked reminder {reminder.id} as sent (no assigned user)'
                        )
                    )
                    continue
                
                # Create notification for valid reminder
                from notifications.signals import create_task_reminder_notification
                create_task_reminder_notification(reminder)
                
                # Mark reminder as sent
                reminder.is_sent = True
                reminder.save(update_fields=['is_sent'])
                processed_count += 1
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Created notification for reminder {reminder.id} (task "{task.title}")'
                    )
                )
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error processing reminder {reminder.id}: {str(e)}'
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Processed {processed_count} reminder(s).'
            )
        )

