"""
Management command to backfill notifications for past events.

This command creates notifications for:
- Past lead assignments (leads with assigned_sales_staff)
- Past task assignments (tasks with assigned_to)
- Past task reminders (reminders that are due or were due)

Usage:
    python manage.py backfill_notifications
    python manage.py backfill_notifications --only-leads
    python manage.py backfill_notifications --only-tasks
    python manage.py backfill_notifications --only-reminders
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from notifications.models import Notification
from notifications.signals import (
    create_lead_assignment_notification,
    create_task_assignment_notification,
    create_task_reminder_notification
)
from employee.models import Employee


class Command(BaseCommand):
    help = 'Backfill notifications for past events (leads, tasks, reminders)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--only-leads',
            action='store_true',
            help='Only backfill lead assignment notifications',
        )
        parser.add_argument(
            '--only-tasks',
            action='store_true',
            help='Only backfill task assignment notifications',
        )
        parser.add_argument(
            '--only-reminders',
            action='store_true',
            help='Only backfill task reminder notifications',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating notifications',
        )

    def handle(self, *args, **options):
        only_leads = options['only_leads']
        only_tasks = options['only_tasks']
        only_reminders = options['only_reminders']
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No notifications will be created'))

        total_created = 0

        # Backfill lead assignment notifications
        if not only_tasks and not only_reminders:
            leads_count = self.backfill_lead_assignments(dry_run)
            total_created += leads_count
            if not dry_run:
                self.stdout.write(
                    self.style.SUCCESS(f'Created {leads_count} lead assignment notification(s)')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Would create {leads_count} lead assignment notification(s)')
                )

        # Backfill task assignment notifications
        if not only_leads and not only_reminders:
            tasks_count = self.backfill_task_assignments(dry_run)
            total_created += tasks_count
            if not dry_run:
                self.stdout.write(
                    self.style.SUCCESS(f'Created {tasks_count} task assignment notification(s)')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Would create {tasks_count} task assignment notification(s)')
                )

        # Backfill task reminder notifications
        if not only_leads and not only_tasks:
            reminders_count = self.backfill_task_reminders(dry_run)
            total_created += reminders_count
            if not dry_run:
                self.stdout.write(
                    self.style.SUCCESS(f'Created {reminders_count} task reminder notification(s)')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Would create {reminders_count} task reminder notification(s)')
                )

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(f'\nTotal notifications created: {total_created}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'\nTotal notifications that would be created: {total_created}')
            )

    def backfill_lead_assignments(self, dry_run=False):
        """Backfill notifications for past lead assignments"""
        from lead.models import Lead

        created_count = 0
        leads = Lead.objects.filter(
            assigned_sales_staff__isnull=False
        ).exclude(assigned_sales_staff='')

        for lead in leads:
            # Check if notification already exists
            employee = self._find_employee_by_name(lead.assigned_sales_staff)
            if not employee:
                continue

            # Check if notification already exists
            existing = Notification.objects.filter(
                user=employee,
                notification_type='lead_assignment',
                lead_id=lead.id
            ).exists()

            if not existing:
                if not dry_run:
                    create_lead_assignment_notification(lead, lead.assigned_sales_staff)
                created_count += 1

        return created_count

    def backfill_task_assignments(self, dry_run=False):
        """Backfill notifications for past task assignments"""
        from task.models import Task

        created_count = 0
        tasks = Task.objects.filter(
            assigned_to__isnull=False,
            is_deleted=False
        )

        for task in tasks:
            # Check if notification already exists
            existing = Notification.objects.filter(
                user=task.assigned_to,
                notification_type='task_assignment',
                task_id=task.id
            ).exists()

            if not existing:
                if not dry_run:
                    create_task_assignment_notification(task, is_new=False)
                created_count += 1

        return created_count

    def backfill_task_reminders(self, dry_run=False):
        """Backfill notifications for past task reminders"""
        from task.models import TaskReminder

        created_count = 0
        # Get all reminders that are due or were due (past reminders)
        now = timezone.now()
        reminders = TaskReminder.objects.filter(remind_at__lte=now)

        for reminder in reminders:
            task = reminder.task
            # Skip if task is deleted, completed, or has no assigned user
            if task.is_deleted or task.status == 'completed' or not task.assigned_to:
                continue

            # Check if notification already exists
            existing = Notification.objects.filter(
                user=task.assigned_to,
                notification_type='task_reminder',
                reminder_id=reminder.id
            ).exists()

            if not existing:
                if not dry_run:
                    create_task_reminder_notification(reminder)
                created_count += 1

        return created_count

    def _find_employee_by_name(self, name):
        """Helper to find employee by name"""
        if not name:
            return None

        # Try to match by first_name + last_name combination
        parts = name.strip().split()
        if len(parts) >= 2:
            # Try exact match on first_name and last_name
            employee = Employee.objects.filter(
                first_name__iexact=parts[0],
                last_name__iexact=' '.join(parts[1:])
            ).first()
            
            if not employee:
                # Try partial match
                employee = Employee.objects.filter(
                    first_name__icontains=parts[0],
                    last_name__icontains=parts[-1]
                ).first()
        else:
            # Single name - try first_name or last_name
            employee = Employee.objects.filter(
                first_name__iexact=name
            ).first()
            if not employee:
                employee = Employee.objects.filter(
                    last_name__iexact=name
                ).first()
        
        return employee

