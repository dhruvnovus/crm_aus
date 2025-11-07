from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from .models import Mail
from .serializers import MailSerializer, CreateTaskFromMailSerializer
from task.models import Task, TaskAttachment, TaskHistory, TaskReminder
from notifications.signals import create_task_reminder_notification, create_task_assignment_notification
from task.serializers import TaskSerializer
from employee.models import Employee


@extend_schema_view(
    list=extend_schema(
        summary="List mails",
        tags=["Mails"],
        parameters=[
            OpenApiParameter(name='employee_id', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=True, description='Owner employee id'),
        ],
    ),
    create=extend_schema(summary="Compose mail", tags=["Mails"], request=MailSerializer),
    retrieve=extend_schema(
        summary="Get mail details",
        tags=["Mails"],
        parameters=[
            OpenApiParameter(name='employee_id', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=True, description='Owner employee id'),
        ],
    ),
    update=extend_schema(summary="Update mail (full)", tags=["Mails"], request=MailSerializer),
    partial_update=extend_schema(summary="Update mail (partial)", tags=["Mails"], request=MailSerializer),
    destroy=extend_schema(summary="Delete mail", tags=["Mails"]),
)
class MailViewSet(viewsets.ModelViewSet):
    queryset = Mail.objects.select_related('linked_task', 'linked_task__assigned_to').filter(is_deleted=False)
    serializer_class = MailSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ['direction', 'status']
    search_fields = ['subject', 'body', 'from_email']
    ordering_fields = ['created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        employee_id = self.request.query_params.get('employee_id')
        if self.request.method in ['GET', 'HEAD', 'OPTIONS']:
            if not employee_id:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'employee_id': 'This query parameter is required.'})
            qs = qs.filter(owner_id=employee_id)
        return qs

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted', 'updated_at'])

    def _actor(self):
        user = getattr(self.request, 'user', None)
        if user and hasattr(user, 'id'):
            return Employee.objects.filter(id=user.id).first()
        return None

    @extend_schema(summary="Create task from mail", tags=["Mails"], request=CreateTaskFromMailSerializer)
    @action(detail=True, methods=['post'])
    def create_task(self, request, pk=None):
        mail = self.get_object()
        serializer = CreateTaskFromMailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        # ensure mail belongs to the same employee
        if str(mail.owner_id) != str(data['employee_id']):
            return Response({'detail': 'employee_id does not match mail owner.'}, status=status.HTTP_400_BAD_REQUEST)

        task = Task.objects.create(
            title=data['title'],
            description=mail.body,
            assigned_to_id=data.get('assigned_to'),
            priority=data.get('priority', 'medium'),
            status='to_do',
            due_date=data['due_date'],
            due_time=data['due_time'],
        )

        # auto link and history record
        mail.linked_task = task
        mail.save(update_fields=['linked_task', 'updated_at'])

        # Create reminders if provided
        reminders = data.get('reminders') or []
        for rm in reminders:
            reminder = TaskReminder.objects.create(task=task, remind_at=rm['remind_at'])
            # also create notification entry linked to this reminder
            create_task_reminder_notification(reminder)

        # Do not create assignment notification here; task post_save signal handles it to avoid duplicates
        # ensure related reminders are visible in response
        task.refresh_from_db()

        TaskHistory.objects.create(
            task=task,
            action='create',
            changed_by=self._actor(),
            changes={'source': 'email', 'mail_id': mail.id}
        )
        # Re-fetch with related reminders to ensure they appear in response
        task = Task.objects.prefetch_related('reminders').get(id=task.id)
        return Response(TaskSerializer(task, context={'request': request}).data, status=status.HTTP_201_CREATED)


