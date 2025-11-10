from rest_framework import serializers

class DashboardLeadItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    email = serializers.EmailField()
    contact = serializers.CharField(allow_blank=True)

class DashboardTaskItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    date = serializers.DateField(source='due_date')
    start_time = serializers.TimeField(source='due_time')
    finish_time = serializers.TimeField(required=False, allow_null=True)
    subject = serializers.CharField(source='title')
    assigned_to = serializers.CharField(allow_blank=True, required=False)
    created_at = serializers.DateTimeField()

class TimeSeriesPointSerializer(serializers.Serializer):
    date = serializers.DateField()
    count = serializers.IntegerField()

class DashboardResponseSerializer(serializers.Serializer):
    # Top tiles
    total_events = serializers.IntegerField()
    total_visitors = serializers.IntegerField()
    total_leads = serializers.IntegerField()
    # Event filter options
    events = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    # Lead status pie
    lead_status_breakdown = serializers.DictField(
        child=serializers.IntegerField()
    )
    # New leads table
    new_leads = DashboardLeadItemSerializer(many=True)
    # Charts
    leads_chart = TimeSeriesPointSerializer(many=True)
    visitors_chart = TimeSeriesPointSerializer(many=True)
    # Follow up tasks
    follow_up_tasks_current = DashboardTaskItemSerializer(many=True)
    follow_up_tasks_completed = DashboardTaskItemSerializer(many=True)
    follow_up_tasks_cancelled = DashboardTaskItemSerializer(many=True)