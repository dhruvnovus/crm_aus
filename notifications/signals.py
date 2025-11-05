"""
Helper functions for creating notifications from other apps
"""
from django.utils import timezone
from .models import Notification
from employee.models import Employee


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
        Notification.objects.create(
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
    else:
        # Log if employee not found (for debugging)
        print(f"Warning: Could not find employee '{assigned_sales_staff}' for lead assignment notification")


def create_task_assignment_notification(task, is_new=False):
    """
    Helper function to create notification when a task is assigned
    """
    if task.assigned_to:
        title = f'New Task Assigned: {task.title}' if is_new else f'Task Assigned: {task.title}'
        message = f'A new task "{task.title}" has been assigned to you.' if is_new else f'Task "{task.title}" has been assigned to you.'
        
        Notification.objects.create(
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


def create_task_reminder_notification(reminder):
    """
    Helper function to create notification when a task reminder is due
    Called from management command or other places
    """
    task = reminder.task
    
    # Only create notification if task has assigned user and is not deleted/completed
    if task.assigned_to and not task.is_deleted and task.status != 'completed':
        Notification.objects.create(
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

