from datetime import timedelta
from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncDate
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from lead.models import Lead
from task.models import Task
from .serializers import DashboardResponseSerializer

class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Dashboard data",
        description="Aggregated data for dashboard tiles, charts, and tables",
        tags=["Dashboard"],
        responses=DashboardResponseSerializer,
        parameters=[
            OpenApiParameter(
                name='event',
                type=OpenApiTypes.STR,
                required=False,
                location=OpenApiParameter.QUERY,
                description="Filter by event name. Omit or use 'All' to include all events."
            ),
            OpenApiParameter(
                name='range',
                type=OpenApiTypes.STR,
                required=False,
                location=OpenApiParameter.QUERY,
                description="Time range for charts. One of: 1m (default), 6m, 1y."
            ),
        ],
    )
    def get(self, request):
        event = request.query_params.get('event')
        rng = (request.query_params.get('range') or '1m').lower()

        queryset = Lead.objects.filter(is_deleted=False)
        if event and event.lower() != 'all':
            queryset = queryset.filter(event=event)

        # Dropdown Events
        events = (
            Lead.objects.filter(is_deleted=False)
            .exclude(event__isnull=True)
            .exclude(event__exact='')
            .values_list('event', flat=True)
            .distinct()
            .order_by('event')
        )

        # Time Range
        days_map = {'1m': 30, '6m': 180, '1y': 365}
        days = days_map.get(rng, 30)
        since_date = timezone.now() - timedelta(days=days)

        # --- Lead Stats ---
        total_leads = queryset.count()
        total_visitors = queryset.filter(lead_type='visitor').count()
        total_events = queryset.exclude(event__isnull=True).exclude(event__exact='').values('event').distinct().count()

        # Status Breakdown
        statuses = [status[0] for status in Lead.STATUS_CHOICES]
        status_counts = {s: 0 for s in statuses}
        for row in queryset.values('status').annotate(count=Count('id')):
            status_counts[row['status']] = row['count']

        # Newest 5 Leads
        new_leads = [
            {
                'id': lead.id,
                'email': lead.email_address,
                'full_name': lead.full_name,
                'contact': lead.contact_number or '',
            }
            for lead in queryset.order_by('-created_at')[:5]
        ]

        # Leads & Visitors (Chart Data)
        leads_last_period = self._get_leads_over_time(queryset, since_date)
        visitors_last_period = self._get_leads_over_time(queryset.filter(lead_type='visitor'), since_date)

        # --- Task Stats ---
        follow_up_tasks_current = self._get_tasks(['to_do', 'in_progress', 'on_hold'])
        follow_up_tasks_completed = self._get_tasks(['completed'])
        follow_up_tasks_cancelled = self._get_tasks([], is_deleted=True)

        payload = {
            'total_events': total_events,
            'total_visitors': total_visitors,
            'total_leads': total_leads,
            'events': list(events),
            'lead_status_breakdown': status_counts,
            'new_leads': new_leads,
            'leads_chart': leads_last_period,
            'visitors_chart': visitors_last_period,
            'follow_up_tasks_current': follow_up_tasks_current,
            'follow_up_tasks_completed': follow_up_tasks_completed,
            'follow_up_tasks_cancelled': follow_up_tasks_cancelled,
        }

        serializer = DashboardResponseSerializer(payload)
        return Response(serializer.data)

    # ----------------------
    # Helper Methods
    # ----------------------

    def _get_leads_over_time(self, queryset, since_date):
        """
        Returns a list of daily counts for leads over a given period.
        """
        return list(
            queryset.filter(created_at__gte=since_date)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )

    def _get_tasks(self, statuses=None, is_deleted=False):
        """
        Returns formatted task data.
        """
        filters = {'is_deleted': is_deleted}
        if statuses:
            filters['status__in'] = statuses

        ordering = '-updated_at' if any(s in ['completed'] for s in statuses or []) else 'due_date'
        tasks = Task.objects.filter(**filters).order_by(ordering, 'due_time')[:10]

        task_data = []
        for task in tasks:
            assigned_name = self._get_assigned_name(task)
            task_data.append({
                'id': task.id,
                'due_date': task.due_date,
                'due_time': task.due_time,
                'finish_time': None,
                'title': task.title,
                'assigned_to': assigned_name,
                'created_at': task.created_at,
            })
        return task_data

    @staticmethod
    def _get_assigned_name(task):
        """
        Returns the best available display name for an assigned user.
        """
        user = task.assigned_to
        if not user:
            return ''
        if getattr(user, 'full_name', None):
            return user.full_name
        return f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
