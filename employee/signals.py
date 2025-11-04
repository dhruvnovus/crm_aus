from django.db.models.signals import post_save, pre_delete
from django.db import transaction
from django.dispatch import receiver
from django.contrib.auth.models import AnonymousUser
from .models import Employee, EmployeeHistory


def build_changes_dict(instance: Employee, created: bool, update_fields=None):
    changes = {}
    if created:
        # record key fields on create
        for field in [
            'account_type', 'staff_type', 'is_active', 'is_resigned', 'title',
            'first_name', 'last_name', 'email', 'position', 'gender'
        ]:
            changes[field] = {'from': None, 'to': getattr(instance, field)}
        return changes
    if update_fields:
        for field in update_fields:
            changes[field] = {'from': getattr(instance._pre_save_snapshot, field, None), 'to': getattr(instance, field)}
    else:
        # fallback best-effort snapshot diff
        for field in [f.name for f in instance._meta.fields]:
            before = getattr(instance._pre_save_snapshot, field, None)
            after = getattr(instance, field)
            if before != after:
                changes[field] = {'from': before, 'to': after}
    return changes


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

