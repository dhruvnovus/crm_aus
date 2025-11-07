from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from lead.models import Lead
from employee.models import Employee
from .serializers import DashboardSummarySerializer
from customers.models import Customer

class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Dashboard summary",
        description="Totals and recent items for dashboard",
        tags=["Dashboard"],
        responses=DashboardSummarySerializer,
    )
    def get(self, request):
        base_qs = Lead.objects.filter(is_deleted=False)

        # Placeholder: will be replaced when Customers API is implemented
        total_customers = Customer.objects.filter(is_deleted=False).count()
        active_leads = base_qs.exclude(status__in=['lost', 'withdrawn', 'converted']).count()
        signed_contracts = base_qs.filter(status='contract_signed').count()
        active_users = Employee.objects.filter(is_active=True, is_resigned=False).count()

        payload = {
            'total_customers': total_customers,
            'active_leads': active_leads,
            'signed_contracts': signed_contracts,
            'active_users': active_users,
        }

        serializer = DashboardSummarySerializer(payload)
        return Response(serializer.data)


