from rest_framework import serializers

class DashboardSummarySerializer(serializers.Serializer):
    total_customers = serializers.IntegerField()
    active_leads = serializers.IntegerField()
    signed_contracts = serializers.IntegerField()
    active_users = serializers.IntegerField()