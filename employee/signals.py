from django.db.models.signals import post_save, pre_save, pre_delete
from django.db import transaction
from django.dispatch import receiver
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from datetime import datetime, date
from .models import Employee, EmployeeHistory


def serialize_value(value):
    """
    Convert datetime/date objects to strings for JSON serialization
    """
    if isinstance(value, datetime):
        return value.isoformat() if value else None
    elif isinstance(value, date):
        return value.isoformat() if value else None
    return value


def build_changes_dict(instance: Employee, created: bool, update_fields=None):
    changes = {}
    if created:
        # record key fields on create
        for field in [
            'account_type', 'staff_type', 'is_active', 'is_resigned', 'title',
            'first_name', 'last_name', 'email', 'position', 'gender'
        ]:
            value = getattr(instance, field)
            changes[field] = {'from': None, 'to': serialize_value(value)}
        return changes
    
    # For updates, we need the snapshot that was created in pre_save
    if not hasattr(instance, '_pre_save_snapshot'):
        # If snapshot doesn't exist, fetch from database
        try:
            old_instance = Employee.objects.get(pk=instance.pk)
            if update_fields:
                for field in update_fields:
                    old_value = getattr(old_instance, field, None)
                    new_value = getattr(instance, field, None)
                    if old_value != new_value:
                        changes[field] = {'from': serialize_value(old_value), 'to': serialize_value(new_value)}
            else:
                # Compare all fields
                for field in [f.name for f in instance._meta.fields]:
                    old_value = getattr(old_instance, field, None)
                    new_value = getattr(instance, field, None)
                    if old_value != new_value:
                        changes[field] = {'from': serialize_value(old_value), 'to': serialize_value(new_value)}
        except Employee.DoesNotExist:
            # If instance doesn't exist in DB yet, treat as create
            pass
        return changes
    
    # Use the snapshot if it exists
    if update_fields:
        for field in update_fields:
            old_value = getattr(instance._pre_save_snapshot, field, None) if hasattr(instance._pre_save_snapshot, field) else None
            new_value = getattr(instance, field, None)
            if old_value != new_value:
                changes[field] = {'from': serialize_value(old_value), 'to': serialize_value(new_value)}
    else:
        # fallback best-effort snapshot diff
        for field in [f.name for f in instance._meta.fields]:
            old_value = getattr(instance._pre_save_snapshot, field, None) if hasattr(instance._pre_save_snapshot, field) else None
            new_value = getattr(instance, field, None)
            if old_value != new_value:
                changes[field] = {'from': serialize_value(old_value), 'to': serialize_value(new_value)}
    return changes


@receiver(pre_save, sender=Employee)
def employee_pre_save(sender, instance: Employee, **kwargs):
    """
    Create a snapshot of the instance before saving to track changes
    """
    if instance.pk:  # Only for updates, not creates
        try:
            # Fetch the current state from database
            old_instance = Employee.objects.get(pk=instance.pk)
            # Create a snapshot by copying the instance
            instance._pre_save_snapshot = old_instance
        except Employee.DoesNotExist:
            # Instance doesn't exist yet, no snapshot needed
            pass


@receiver(post_save, sender=Employee)
def employee_saved(sender, instance: Employee, created, **kwargs):
    request = getattr(instance, '_request', None)
    user = None
    if request and hasattr(request, 'user') and not isinstance(request.user, AnonymousUser):
        user = request.user

    changes = build_changes_dict(instance, created, kwargs.get('update_fields'))
    if not changes:
        return
    
    # Defer history creation to after transaction commits to avoid blocking the response
    # This improves performance, especially for slow database connections
    def create_history():
        EmployeeHistory.objects.create(
            employee=instance,
            action='create' if created else 'update',
            changed_by=user,
            changes=changes
        )
    
    transaction.on_commit(create_history)


@receiver(pre_delete, sender=Employee)
def employee_deleted(sender, instance: Employee, **kwargs):
    EmployeeHistory.objects.create(
        employee=instance,
        action='delete',
        changed_by=None,
        changes={'id': {'from': instance.id, 'to': None}, 'email': {'from': instance.email, 'to': None}}
    )

