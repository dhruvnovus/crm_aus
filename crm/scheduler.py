"""
APScheduler configuration for task reminders
"""
import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from django.utils import timezone
from task.models import TaskReminder
from task.sse import send_reminder_sse_event

logger = logging.getLogger("dea_crm")

# Global scheduler instance
scheduler = None


def reminder_job():
    """
    Job that runs periodically to check for due reminders and send SSE events.
    This runs every 30 seconds.
    """
    try:
        now = timezone.now()
        
        # Find reminders that are due and not yet sent
        due_reminders = TaskReminder.objects.filter(
            remind_at__lte=now,
            is_sent=False
        ).select_related('task', 'task__assigned_to')
        
        if not due_reminders.exists():
            logger.debug('No reminders due at this time.')
            return
        
        processed_count = 0
        
        for reminder in due_reminders:
            try:
                task = reminder.task
                
                # Skip if task is deleted or completed
                if task.is_deleted or task.status == 'completed':
                    reminder.is_sent = True
                    reminder.save(update_fields=['is_sent'])
                    processed_count += 1
                    logger.info(f'Marked reminder {reminder.id} as sent (task {task.id} is {"deleted" if task.is_deleted else "completed"})')
                    continue
                
                # Skip if no assigned user
                if not task.assigned_to:
                    reminder.is_sent = True
                    reminder.save(update_fields=['is_sent'])
                    processed_count += 1
                    logger.info(f'Marked reminder {reminder.id} as sent (no assigned user)')
                    continue
                
                # Prepare reminder payload
                payload = {
                    "type": "reminder",
                    "task_id": task.id,
                    "task_title": task.title,
                    "task_description": task.description or "",
                    "reminder_id": reminder.id,
                    "remind_at": reminder.remind_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "due_date": str(task.due_date),
                    "due_time": str(task.due_time),
                    "priority": task.priority,
                }
                
                # Send SSE event to the assigned user
                user_id = task.assigned_to.id
                send_reminder_sse_event(user_id, "reminder", payload)
                
                # Mark reminder as sent
                reminder.is_sent = True
                reminder.save(update_fields=['is_sent'])
                
                processed_count += 1
                logger.info(f'Sent reminder {reminder.id} for task "{task.title}" to user {user_id}')
                    
            except Exception as e:
                logger.error(f'Error processing reminder {reminder.id}: {str(e)}', exc_info=True)
        
        if processed_count > 0:
            logger.info(f'Processed {processed_count} reminder(s)')
            
    except Exception as e:
        logger.error(f'Error in reminder_job: {str(e)}', exc_info=True)


def start_scheduler():
    """
    Start the APScheduler background scheduler.
    Only starts once, even in multi-worker setups.
    """
    global scheduler
    
    # Check if we're in the main process (not a worker subprocess)
    # This prevents multiple schedulers from starting in gunicorn multi-worker setups
    import sys
    is_gunicorn_worker = 'gunicorn' in os.environ.get('_', '') or 'gunicorn' in str(sys.argv)
    is_main_process = os.environ.get('RUN_MAIN') == 'true'
    
    if is_gunicorn_worker and not is_main_process:
        logger.info('Skipping scheduler start (not main process in gunicorn)')
        return
    
    if scheduler is not None and scheduler.running:
        logger.info('Scheduler already running')
        return
    
    try:
        scheduler = BackgroundScheduler()
        # Run reminder check every 10 seconds (user changed from 30 to 10)
        scheduler.add_job(
            reminder_job,
            'interval',
            seconds=10,
            id='check_reminders',
            replace_existing=True
        )
        scheduler.start()
        logger.info('APScheduler started successfully - checking reminders every 10 seconds')
    except Exception as e:
        logger.error(f'Failed to start scheduler: {str(e)}', exc_info=True)


def stop_scheduler():
    """Stop the scheduler (useful for testing)"""
    global scheduler
    if scheduler is not None and scheduler.running:
        scheduler.shutdown()
        logger.info('Scheduler stopped')

