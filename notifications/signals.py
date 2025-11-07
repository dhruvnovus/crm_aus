"""
Helper functions for creating notifications from other apps
"""
from django.utils import timezone
from .models import Notification
from employee.models import Employee
from .sse import publisher


def _serialize_notification_for_sse(notification):
    """
    Serialize notification for SSE without requiring request context.
    This is a simplified version that works without DRF serializer context.
    """
    data = {
        'id': notification.id,
        'user': notification.user.id,
        'notification_type': notification.notification_type,
        'title': notification.title,
        'message': notification.message,
        'lead_id': notification.lead_id,
        'task_id': notification.task_id,
        'reminder_id': notification.reminder_id,
        'metadata': notification.metadata,
        'is_read': notification.is_read,
        'read_at': notification.read_at.isoformat() if notification.read_at else None,
        'created_at': notification.created_at.isoformat(),
        'updated_at': notification.updated_at.isoformat(),
    }
    
    # Add lead_data if applicable
    if notification.notification_type == 'lead_assignment' and notification.lead_id:
        try:
            from lead.models import Lead
            lead = Lead.objects.get(id=notification.lead_id)
            data['lead_data'] = {
                'id': lead.id,
                'full_name': lead.full_name,
                'company_name': lead.company_name,
                'email_address': lead.email_address,
                'contact_number': lead.contact_number,
                'status': lead.status,
                'lead_type': lead.lead_type,
            }
        except Exception:
            data['lead_data'] = None
    
    # Add task_data if applicable
    if notification.notification_type in ['task_assignment', 'task_reminder'] and notification.task_id:
        try:
            from task.models import Task
            task = Task.objects.get(id=notification.task_id)
            data['task_data'] = {
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'priority': task.priority,
                'status': task.status,
                'due_date': task.due_date.isoformat(),
                'due_time': task.due_time.isoformat(),
            }
        except Exception:
            data['task_data'] = None
    
    # Add reminder_data if applicable
    if notification.notification_type == 'task_reminder' and notification.reminder_id:
        try:
            from task.models import TaskReminder
            reminder = TaskReminder.objects.get(id=notification.reminder_id)
            data['reminder_data'] = {
                'id': reminder.id,
                'remind_at': reminder.remind_at.isoformat(),
                'is_sent': reminder.is_sent,
            }
        except Exception:
            data['reminder_data'] = None
    
    return data


def create_lead_assignment_notification(lead, assigned_sales_staff):
    """
    Helper function to create notification when a lead is assigned
    Called from lead views when assignment happens
    Now accepts Employee object directly instead of name
    """
    if not assigned_sales_staff:
        return
    
    # assigned_sales_staff is now an Employee object (ForeignKey)
    if isinstance(assigned_sales_staff, Employee):
        employee = assigned_sales_staff
    else:
        # Fallback: if it's still a string/name (for backward compatibility during migration)
        parts = str(assigned_sales_staff).strip().split()
        employee = None
        
        if len(parts) >= 2:
            employee = Employee.objects.filter(
                first_name__iexact=parts[0],
                last_name__iexact=' '.join(parts[1:])
            ).first()
            
            if not employee:
                employee = Employee.objects.filter(
                    first_name__icontains=parts[0],
                    last_name__icontains=parts[-1]
                ).first()
        else:
            employee = Employee.objects.filter(
                first_name__iexact=str(assigned_sales_staff)
            ).first()
            if not employee:
                employee = Employee.objects.filter(
                    last_name__iexact=str(assigned_sales_staff)
                ).first()
    
    if employee:
        notification = Notification.objects.create(
            user=employee,
            notification_type='lead_assignment',
            title=f'Lead Assigned: {lead.full_name}',
            message=f'A new lead "{lead.full_name}" from {lead.company_name} has been assigned to you.',
            lead_id=lead.id,
            metadata={
                'lead_name': lead.full_name,
                'company_name': lead.company_name,
                'email': lead.email_address,
                'status': lead.status,
                'lead_type': lead.lead_type,
            }
        )
        
        # Publish SSE event for real-time notification
        try:
            notification_data = _serialize_notification_for_sse(notification)
            publisher.publish(
                user_id=employee.id,
                event_type='notification',
                data=notification_data
            )
            # Debug logging
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Published SSE notification for employee_id={employee.id}, notification_id={notification.id}, lead_id={lead.id}")
        except Exception as e:
            # Log error but don't fail notification creation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to publish SSE event for notification {notification.id}: {str(e)}", exc_info=True)
    else:
        # Log if employee not found (for debugging)
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not find employee '{assigned_sales_staff}' for lead assignment notification (lead_id={lead.id})")


def create_task_assignment_notification(task, is_new=False):
    """
    Helper function to create notification when a task is assigned
    """
    if task.assigned_to:
        title = f'New Task Assigned: {task.title}' if is_new else f'Task Assigned: {task.title}'
        message = f'A new task "{task.title}" has been assigned to you.' if is_new else f'Task "{task.title}" has been assigned to you.'
        
        notification = Notification.objects.create(
            user=task.assigned_to,
            notification_type='task_assignment',
            title=title,
            message=message,
            task_id=task.id,
            metadata={
                'priority': task.priority,
                'due_date': str(task.due_date),
                'due_time': str(task.due_time),
                'status': task.status,
            }
        )
        
        # Publish SSE event for real-time notification
        notification_data = _serialize_notification_for_sse(notification)
        publisher.publish(
            user_id=task.assigned_to.id,
            event_type='notification',
            data=notification_data
        )


def create_task_reminder_notification(reminder):
    """
    Helper function to create notification when a task reminder is due
    Called from management command or other places
    """
    task = reminder.task
    
    # Only create notification if task has assigned user and is not deleted/completed
    if task.assigned_to and not task.is_deleted and task.status != 'completed':
        notification = Notification.objects.create(
            user=task.assigned_to,
            notification_type='task_reminder',
            title=f'Task Reminder: {task.title}',
            message=f'Task "{task.title}" is due on {task.due_date} at {task.due_time}',
            task_id=task.id,
            reminder_id=reminder.id,
            metadata={
                'priority': task.priority,
                'due_date': str(task.due_date),
                'due_time': str(task.due_time),
                'remind_at': reminder.remind_at.isoformat(),
            }
        )
        
        # Publish SSE event for real-time notification
        notification_data = _serialize_notification_for_sse(notification)
        publisher.publish(
            user_id=task.assigned_to.id,
            event_type='notification',
            data=notification_data
        )

