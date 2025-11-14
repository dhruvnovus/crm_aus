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
from .models import Task, TaskHistory, TaskAttachment, Subtask
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
        if not user:
            return None

        # Primary resolution path: email/username
        user_email = getattr(user, 'email', None) or getattr(user, 'username', None)
        if user_email:
            employee = Employee.objects.filter(email=user_email, is_active=True).first()
            if employee:
                return employee

        # Fallback: direct id match (for backward compatibility)
        if hasattr(user, 'id'):
            return Employee.objects.filter(id=user.id).first()
        return None

    @extend_schema(
        summary="Get my tasks",
        description="Get all tasks assigned to the current authenticated user",
        tags=["Tasks"],
        responses={200: TaskSerializer(many=True)},
    )
    @action(detail=False, methods=['get'], url_path='my_tasks')
    def my_tasks(self, request):
        """Get all tasks assigned to the current user"""
        # Get the employee linked to this user by email (Employee and User are linked by email)
        user_email = getattr(request.user, 'email', None) or getattr(request.user, 'username', None)
        if not user_email:
            return Response(
                {'detail': 'User email not found.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        employee = Employee.objects.filter(email=user_email, is_active=True).first()
        if not employee:
            return Response(
                {'detail': 'No employee record found for this user.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        qs = self.get_queryset().filter(assigned_to=employee)
        
        # Apply pagination
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


    @extend_schema(
        summary="Get tasks due today",
        description="Get all tasks that are due today",
        tags=["Tasks"],
        responses={200: TaskSerializer(many=True)},
    )
    @action(detail=False, methods=['get'], url_path='due_today')
    def due_today(self, request):
        """Get all tasks due today"""
        today = timezone.localdate()
        qs = self.get_queryset().filter(due_date=today)
        
        # Apply pagination
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


    @extend_schema(
        summary="Get overdue tasks",
        description="Get all tasks that are overdue (not completed and due date is in the past)",
        tags=["Tasks"],
        responses={200: TaskSerializer(many=True)},
    )
    @action(detail=False, methods=['get'], url_path='overdue')
    def overdue(self, request):
        """Get all overdue tasks (not completed and due date < today)"""
        today = timezone.localdate()
        qs = self.get_queryset().filter(
            ~Q(status='completed'),
            due_date__lt=today
        )
        
        # Apply pagination
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

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
        # Store task title before deletion for subtask history
        task_title = instance.title
        
        # If this task is a subtask of other tasks, create history in parent tasks
        parent_tasks = Task.objects.filter(subtasks__child_task=instance, is_deleted=False).distinct()
        for parent_task in parent_tasks:
            # Find the subtask relationship
            subtask = parent_task.subtasks.filter(child_task=instance).first()
            if subtask:
                # Create history in parent task showing subtask was deleted
                TaskHistory.objects.create(
                    task=parent_task,
                    action='subtask_delete',
                    changed_by=self._actor(),
                    changes={
                        'subtasks': {
                            'added': [],
                            'removed': [{'name': task_title}]
                        }
                    }
                )
                # Delete the subtask relationship
                subtask.delete()
        
        # Mark task as deleted
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
        # Track all editable fields
        prev_values = {
            'assigned_to': old.assigned_to_id,
            'status': old.status,
            'priority': old.priority,
            'title': old.title,
            'description': old.description,
            'due_date': old.due_date,
            'due_time': old.due_time,
        }
        
        # Track subtasks, reminders, and attachments before update
        prev_subtasks = sorted(list(old.subtasks.values_list('child_task_id', flat=True)))
        prev_reminders = sorted([(r.remind_at.isoformat() if r.remind_at else None) for r in old.reminders.all()])
        prev_attachments = sorted([a.filename for a in old.attachments.all()])
        
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
        
        # Refresh to get updated relationships
        task.refresh_from_db()
        
        # Track all changes
        changes = {}
        
        # Track basic fields
        if prev_values['assigned_to'] != task.assigned_to_id:
            from_employee = None
            if prev_values['assigned_to']:
                from_employee = Employee.objects.filter(id=prev_values['assigned_to']).first()
            to_employee = task.assigned_to
            changes['assigned_to'] = {
                'from': {
                    'name': from_employee.full_name if from_employee else None
                },
                'to': {
                    'name': to_employee.full_name if to_employee else None
                }
            }
        if prev_values['status'] != task.status:
            changes['status'] = {'from': prev_values['status'], 'to': task.status}
        if prev_values['priority'] != task.priority:
            changes['priority'] = {'from': prev_values['priority'], 'to': task.priority}
        if prev_values['title'] != task.title:
            changes['title'] = {'from': prev_values['title'], 'to': task.title}
        if prev_values['description'] != task.description:
            changes['description'] = {'from': prev_values['description'], 'to': task.description}
        
        # Track due_date and due_time
        if prev_values['due_date'] != task.due_date:
            changes['due_date'] = {'from': prev_values['due_date'].isoformat() if prev_values['due_date'] else None, 'to': task.due_date.isoformat() if task.due_date else None}
        if prev_values['due_time'] != task.due_time:
            changes['due_time'] = {'from': prev_values['due_time'].isoformat() if prev_values['due_time'] else None, 'to': task.due_time.isoformat() if task.due_time else None}
        
        # Track subtasks changes
        new_subtasks = sorted(list(task.subtasks.values_list('child_task_id', flat=True)))
        if prev_subtasks != new_subtasks:
            # Find added and removed subtasks
            added_ids = [task_id for task_id in new_subtasks if task_id not in prev_subtasks]
            removed_ids = [task_id for task_id in prev_subtasks if task_id not in new_subtasks]

            added = []
            removed = []
            if added_ids:
                added_tasks = Task.objects.filter(id__in=added_ids).values('id', 'title')
                added = [{'name': t['title']} for t in added_tasks]
            if removed_ids:
                removed_tasks = Task.objects.filter(id__in=removed_ids).values('id', 'title')
                removed = [{'name': t['title']} for t in removed_tasks]

            if added or removed:
                changes['subtasks'] = {
                    'added': added,
                    'removed': removed
                }
        
        # Track reminders changes
        new_reminders = sorted([(r.remind_at.isoformat() if r.remind_at else None) for r in task.reminders.all()])
        if prev_reminders != new_reminders:
            changes['reminders'] = {
                'from': prev_reminders,
                'to': new_reminders
            }
        
        # Track attachments changes (new files added during update)
        new_attachments = sorted([a.filename for a in task.attachments.all()])
        if prev_attachments != new_attachments:
            # Find added and removed attachments
            added = [f for f in new_attachments if f not in prev_attachments]
            removed = [f for f in prev_attachments if f not in new_attachments]
            if added or removed:
                changes['attachments'] = {
                    'added': added,
                    'removed': removed
                }
        
        # Create notification if task is assigned to a new user
        if 'assigned_to' in changes and task.assigned_to:
            from notifications.signals import create_task_assignment_notification
            create_task_assignment_notification(task, is_new=False)
        
        # Determine action type based on which field(s) changed
        # Priority: single field changes get specific action, multiple changes = 'update'
        if len(changes) == 1:
            field_name = list(changes.keys())[0]
            # Map field names to action names
            action_map = {
                'assigned_to': 'assign',
                'status': 'status_change',
                'priority': 'priority_change',
                'title': 'title_change',
                'description': 'description_change',
                'due_date': 'due_date_change',
                'due_time': 'due_time_change',
                'subtasks': 'subtask_change',
                'reminders': 'reminder_change',
                'attachments': 'attachment_change',
            }
            action = action_map.get(field_name, 'update')
        else:
            action = 'update'
        
        # Only create history if there are changes
        if changes:
            TaskHistory.objects.create(
                task=task,
                action=action,
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
        # Allow accessing history even for deleted tasks
        try:
            task = Task.objects.get(pk=pk)  # Get task without is_deleted filter
        except Task.DoesNotExist:
            return Response({'detail': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)
        
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
        added_filenames = []
        for uploaded_file in files:
            attachment = TaskAttachment.objects.create(
                task=task,
                file=uploaded_file,
                filename=uploaded_file.name
            )
            attachments.append(attachment)
            added_filenames.append(uploaded_file.name)
        
        # Create history entry with same format as update (added/removed)
        TaskHistory.objects.create(
            task=task,
            action='attachment_add',
            changed_by=self._actor(),
            changes={
                'attachments': {
                    'added': added_filenames,
                    'removed': []
                }
            }
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
                changes={
                    'attachments': {
                        'added': [],
                        'removed': [filename]
                    }
                }
            )
            
            return Response({'detail': 'Attachment deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
        except TaskAttachment.DoesNotExist:
            raise Http404("Attachment not found")