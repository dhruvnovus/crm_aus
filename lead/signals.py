from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from .models import Lead, LeadHistory
from decimal import Decimal
from datetime import datetime, date


def _serialize_value(value):
    if isinstance(value, Decimal):
        # convert Decimal to string to preserve precision in JSON
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def build_changes_dict(instance: Lead, created: bool, update_fields=None):
    changes = {}
    interesting_fields = [
        'status', 'intensity', 'assigned_sales_staff', 'opportunity_price',
        'lead_type', 'event', 'first_name', 'last_name', 'company_name'
    ]
    if created:
        for f in interesting_fields:
            changes[f] = {'from': None, 'to': _serialize_value(getattr(instance, f))}
        return changes
    fields = update_fields or interesting_fields
    for f in fields:
        before = _serialize_value(getattr(instance._pre_save_snapshot, f, None)) if hasattr(instance, '_pre_save_snapshot') else None
        after = _serialize_value(getattr(instance, f))
        if before != after:
            changes[f] = {'from': before, 'to': after}
    return changes


@receiver(post_save, sender=Lead)
def lead_saved(sender, instance: Lead, created, **kwargs):
    changes = build_changes_dict(instance, created, kwargs.get('update_fields'))
    if changes:
        LeadHistory.objects.create(
            lead=instance,
            action='create' if created else 'update',
            changed_by=None,
            changes=changes
        )


@receiver(pre_delete, sender=Lead)
def lead_deleted(sender, instance: Lead, **kwargs):
    LeadHistory.objects.create(
        lead=instance,
        action='delete',
        changed_by=None,
        changes={'id': {'from': instance.id, 'to': None}}
    )

