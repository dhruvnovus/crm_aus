#!/usr/bin/env python
"""
Test script to manually publish a notification and verify SSE works
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm.settings')
django.setup()

from lead.models import Lead
from employee.models import Employee
from notifications.signals import create_lead_assignment_notification
from notifications.sse import publisher

# Test parameters
lead_id = 22
employee_id = 6

print(f"Testing notification for Lead ID {lead_id} assigned to Employee ID {employee_id}")
print("=" * 60)

# Get the lead and employee
try:
    lead = Lead.objects.get(id=lead_id)
    print(f"✓ Found Lead: {lead.full_name}")
except Lead.DoesNotExist:
    print(f"✗ Lead with ID {lead_id} not found")
    sys.exit(1)

try:
    employee = Employee.objects.get(id=employee_id, is_deleted=False)
    print(f"✓ Found Employee: {employee.first_name} {employee.last_name} (ID: {employee.id})")
except Employee.DoesNotExist:
    print(f"✗ Employee with ID {employee_id} not found or is deleted")
    sys.exit(1)

# Check if employee has active SSE subscription
print("\nChecking SSE subscription status:")
with publisher._lock:
    if employee_id in publisher._queues:
        queue_size = publisher._queues[employee_id].qsize()
        print(f"✓ Employee {employee_id} has active SSE subscription (queue size: {queue_size})")
    else:
        print(f"⚠ Employee {employee_id} does NOT have an active SSE subscription")
        print("  (This means no client is currently connected to the stream)")
        print("  The notification will still be created in the database, but won't be sent via SSE")

# Create notification
print("\nCreating notification...")
try:
    create_lead_assignment_notification(lead, employee)
    print("✓ Notification created successfully")
    
    # Check if notification was created in DB
    from notifications.models import Notification
    notification = Notification.objects.filter(
        user=employee,
        notification_type='lead_assignment',
        lead_id=lead_id
    ).order_by('-created_at').first()
    
    if notification:
        print(f"✓ Notification found in database (ID: {notification.id})")
        print(f"  Title: {notification.title}")
    else:
        print("✗ Notification not found in database")
        
except Exception as e:
    print(f"✗ Error creating notification: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Check if event was published
print("\nChecking if SSE event was published...")
with publisher._lock:
    if employee_id in publisher._queues:
        queue_size_after = publisher._queues[employee_id].qsize()
        if queue_size_after > queue_size:
            print(f"✓ Event published to queue (queue size increased from {queue_size} to {queue_size_after})")
        else:
            print(f"⚠ Event may not have been published (queue size: {queue_size_after})")
    else:
        print("⚠ No active subscription, event was not published to queue")

print("\n" + "=" * 60)
print("Test complete!")
print("\nTo test with SSE stream:")
print(f"1. Connect to SSE stream with employee_id={employee_id}'s JWT token")
print(f"2. Assign lead {lead_id} to employee {employee_id} again")
print(f"3. You should see the notification in the stream")

