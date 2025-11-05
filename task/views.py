from django.utils import timezone
from django.db.models import Q
from django.http import FileResponse, Http404
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db import transaction, IntegrityError
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from .models import Task, TaskHistory, TaskAttachment
from employee.models import Employee
from .serializers import TaskSerializer, TaskHistorySerializer, TaskAttachmentSerializer


@extend_schema_view(
    list=extend_schema(
        summary="List all tasks",
        description="Get a paginated list of all tasks with optional filtering",
        tags=["Tasks"],
    ),
    create=extend_schema(
        summary="Create task",
        description="Create a new task. Use multipart/form-data content type to upload files in the 'files' field.",
        tags=["Tasks"],
        request=TaskSerializer,
    ),
    retrieve=extend_schema(
        summary="Get task details",
        description="Retrieve detailed information about a specific task",
        tags=["Tasks"],
    ),
    update=extend_schema(
        summary="Update task (full)",
        description="Update all fields of a task. Use multipart/form-data content type to upload files in the 'files' field.",
        tags=["Tasks"],
        request=TaskSerializer,
    ),
    partial_update=extend_schema(
        summary="Update task (partial)",
        description="Update specific fields of a task. Use multipart/form-data content type to upload files in the 'files' field.",
        tags=["Tasks"],
        request=TaskSerializer,
    ),
    destroy=extend_schema(
        summary="Delete task",
        description="Delete a task from the system (soft delete)",
        tags=["Tasks"],
    ),
)
class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.filter(is_deleted=False)
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ['priority', 'status', 'assigned_to']
    search_fields = ['title', 'description']
    ordering_fields = ['due_date', 'priority', 'created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        filter_key = self.request.query_params.get('filter')
        today = timezone.localdate()

        if filter_key == 'my':
            if hasattr(self.request.user, 'id'):
                qs = qs.filter(assigned_to_id=self.request.user.id)
        elif filter_key == 'due_today':
            qs = qs.filter(due_date=today)
        elif filter_key == 'overdue':
            qs = qs.filter(~Q(status='completed'), due_date__lt=today)
        # default 'all' keeps qs as is
        return qs

    def _actor(self):
        user = getattr(self.request, 'user', None)
        if user and hasattr(user, 'id'):
            # Try to resolve to Employee instance; return None if not found
            return Employee.objects.filter(id=user.id).first()
        return None

    @extend_schema(
        summary="Mark task as completed",
        description="Mark a task as completed",
        tags=["Tasks"],
    )
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        task = self.get_object()
        task.status = 'completed'
        task.save(update_fields=['status', 'updated_at'])
        TaskHistory.objects.create(
            task=task, action='status_change', changed_by=self._actor(),
            changes={'status': {'to': 'completed'}}
        )
        return Response(self.get_serializer(task).data)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted', 'updated_at'])
        TaskHistory.objects.create(task=instance, action='delete', changed_by=self._actor())

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                # Get files from request.FILES
                files = self.request.FILES.getlist('files', [])
                # Pass files to serializer via context
                serializer.context['files'] = files
                task = serializer.save()
                TaskHistory.objects.create(task=task, action='create', changed_by=self._actor())
        except (IntegrityError, ValueError) as exc:
            raise ValidationError({'detail': str(exc)})

    def perform_update(self, serializer):
        old = self.get_object()
        prev_values = {
            'assigned_to': old.assigned_to_id,
            'status': old.status,
            'priority': old.priority,
            'title': old.title,
        }
        try:
            with transaction.atomic():
                # Get files from request.FILES if any
                files = self.request.FILES.getlist('files', [])
                # Pass files to serializer via context (only if files were provided)
                if files:
                    serializer.context['files'] = files
                task = serializer.save()
        except (IntegrityError, ValueError) as exc:
            raise ValidationError({'detail': str(exc)})
        changes = {}
        if prev_values['assigned_to'] != task.assigned_to_id:
            changes['assigned_to'] = {'from': prev_values['assigned_to'], 'to': task.assigned_to_id}
            action = 'assign'
            
            # Create notification if task is assigned to a new user
            if task.assigned_to:
                from notifications.signals import create_task_assignment_notification
                create_task_assignment_notification(task, is_new=False)
        if prev_values['status'] != task.status:
            changes['status'] = {'from': prev_values['status'], 'to': task.status}
        if prev_values['priority'] != task.priority:
            changes['priority'] = {'from': prev_values['priority'], 'to': task.priority}
        if prev_values['title'] != task.title:
            changes['title'] = {'from': prev_values['title'], 'to': task.title}
        TaskHistory.objects.create(
            task=task,
            action='assign' if 'assigned_to' in changes and len(changes) == 1 else ('status_change' if 'status' in changes and len(changes) == 1 else 'update'),
            changed_by=self._actor(),
            changes=changes,
        )

    @extend_schema(
        summary="Get or add task history",
        description="GET: Retrieve task history entries. POST: Add a comment to task history.",
        tags=["Tasks"],
        responses={200: TaskHistorySerializer(many=True), 201: TaskHistorySerializer},
    )
    @action(detail=True, methods=['get', 'post'])
    def history(self, request, pk=None):
        task = self.get_object()
        if request.method.lower() == 'post':
            note = request.data.get('note', '')
            entry = TaskHistory.objects.create(task=task, action='comment', note=note, changed_by=self._actor())
            return Response(TaskHistorySerializer(entry).data)
        entries = task.history_entries.all()
        return Response(TaskHistorySerializer(entries, many=True).data)

    @extend_schema(
        summary="Upload attachments to task",
        description="Upload one or more files as attachments to a task. Use multipart/form-data with a 'files' field containing the file(s).",
        tags=["Tasks"],
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'files': {
                        'type': 'array',
                        'items': {'type': 'string', 'format': 'binary'},
                        'description': 'List of files to upload'
                    }
                },
                'required': ['files']
            }
        },
        responses={201: TaskAttachmentSerializer(many=True)},
    )
    @action(detail=True, methods=['post'])
    def upload_attachments(self, request, pk=None):
        """Upload one or more files as attachments to a task"""
        task = self.get_object()
        files = request.FILES.getlist('files')
        
        if not files:
            raise ValidationError({'detail': 'No files provided'})
        
        attachments = []
        for uploaded_file in files:
            attachment = TaskAttachment.objects.create(
                task=task,
                file=uploaded_file,
                filename=uploaded_file.name
            )
            attachments.append(attachment)
            # Create history entry
            TaskHistory.objects.create(
                task=task,
                action='attachment_add',
                changed_by=self._actor(),
                changes={'filename': uploaded_file.name}
            )
        
        serializer = TaskAttachmentSerializer(attachments, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="List task attachments",
        description="List all attachments for a task",
        tags=["Tasks"],
        responses={200: TaskAttachmentSerializer(many=True)},
    )
    @action(detail=True, methods=['get'])
    def attachments(self, request, pk=None):
        """List all attachments for a task"""
        task = self.get_object()
        attachments = task.attachments.all()
        serializer = TaskAttachmentSerializer(attachments, many=True, context={'request': request})
        return Response(serializer.data)

    @extend_schema(
        summary="Download task attachment",
        description="Download a specific attachment file from a task",
        tags=["Tasks"],
        responses={200: OpenApiTypes.BINARY},
    )
    @action(detail=True, methods=['get'], url_path='attachments/(?P<attachment_id>[^/.]+)/download')
    def download_attachment(self, request, pk=None, attachment_id=None):
        """Download a specific attachment file from a task"""
        task = self.get_object()
        try:
            attachment = TaskAttachment.objects.get(id=attachment_id, task=task)
            if not attachment.file:
                raise Http404("File not found")
            
            response = FileResponse(
                attachment.file.open(),
                content_type=attachment.content_type or 'application/octet-stream'
            )
            response['Content-Disposition'] = f'attachment; filename="{attachment.filename}"'
            return response
        except TaskAttachment.DoesNotExist:
            raise Http404("Attachment not found")

    @extend_schema(
        summary="Delete task attachment",
        description="Delete a specific attachment from a task",
        tags=["Tasks"],
        responses={204: None},
    )
    @action(detail=True, methods=['delete'], url_path='attachments/(?P<attachment_id>[^/.]+)')
    def delete_attachment(self, request, pk=None, attachment_id=None):
        """Delete a specific attachment from a task"""
        task = self.get_object()
        try:
            attachment = TaskAttachment.objects.get(id=attachment_id, task=task)
            filename = attachment.filename
            
            # Delete the file from storage
            if attachment.file:
                attachment.file.delete(save=False)
            
            # Delete the attachment record
            attachment.delete()
            
            # Create history entry
            TaskHistory.objects.create(
                task=task,
                action='attachment_remove',
                changed_by=self._actor(),
                changes={'filename': filename}
            )
            
            return Response({'detail': 'Attachment deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
        except TaskAttachment.DoesNotExist:
            raise Http404("Attachment not found")


