"""
Notification serializers
"""
from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model"""
    lead_data = serializers.SerializerMethodField()
    task_data = serializers.SerializerMethodField()
    reminder_data = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'notification_type', 'title', 'message',
            'lead_id', 'task_id', 'reminder_id', 'metadata',
            'lead_data', 'task_data', 'reminder_data',
            'is_read', 'read_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'read_at']
    
    def get_lead_data(self, obj):
        """Get lead details if notification type is lead_assignment"""
        if obj.notification_type == 'lead_assignment' and obj.lead_id:
            try:
                from lead.models import Lead
                lead = Lead.objects.get(id=obj.lead_id)
                return {
                    'id': lead.id,
                    'full_name': lead.full_name,
                    'company_name': lead.company_name,
                    'email_address': lead.email_address,
                    'contact_number': lead.contact_number,
                    'status': lead.status,
                    'lead_type': lead.lead_type,
                }
            except Lead.DoesNotExist:
                return None
        return None
    
    def get_task_data(self, obj):
        """Get task details if notification type is task_assignment or task_reminder"""
        if obj.notification_type in ['task_assignment', 'task_reminder'] and obj.task_id:
            try:
                from task.models import Task
                task = Task.objects.get(id=obj.task_id)
                return {
                    'id': task.id,
                    'title': task.title,
                    'description': task.description,
                    'priority': task.priority,
                    'status': task.status,
                    'due_date': task.due_date.isoformat(),
                    'due_time': task.due_time.isoformat(),
                }
            except Task.DoesNotExist:
                return None
        return None
    
    def get_reminder_data(self, obj):
        """Get reminder details if notification type is task_reminder"""
        if obj.notification_type == 'task_reminder' and obj.reminder_id:
            try:
                from task.models import TaskReminder
                reminder = TaskReminder.objects.get(id=obj.reminder_id)
                return {
                    'id': reminder.id,
                    'remind_at': reminder.remind_at.isoformat(),
                    'is_sent': reminder.is_sent,
                }
            except TaskReminder.DoesNotExist:
                return None
        return None

