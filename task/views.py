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
from .models import Task, TaskHistory, TaskAttachment, Subtask, TaskReminder
from employee.models import Employee
from .serializers import TaskSerializer, TaskHistorySerializer, TaskAttachmentSerializer
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken
from django.contrib.auth.models import User
from task.sse import sse_reminder_stream

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

    @extend_schema(
        summary="SSE stream for task reminders",
        description="Server-Sent Events stream for receiving real-time task reminders. "
                    "Requires authentication via JWT token.\n\n"
                    "**For browser clients (EventSource API):** Use `?token=<jwt_token>` query parameter "
                    "(EventSource doesn't support custom headers).\n\n"
                    "**For non-browser clients:** Use `Authorization: Bearer <jwt_token>` header.",
        tags=["Tasks"],
        parameters=[
            OpenApiParameter(
                name='token',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description='JWT token for authentication (required for browser EventSource API)'
            ),
        ],
    )
    @action(detail=False, methods=['get'], url_path='reminders/stream')
    def reminder_stream(self, request):
        """
        SSE endpoint for streaming real-time task reminders.
        Connects to the reminder event stream for the authenticated user.
        """
       
        employee = None
        token = None
        
        # Try to get token from Authorization header first
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        # Fallback to query parameter if no Authorization header
        if not token:
            token = request.query_params.get('token')
        
        if token:
            try:
                untyped_token = UntypedToken(token)
                user_id = getattr(untyped_token, 'payload', {}).get('user_id')
                if user_id:
                    django_user = User.objects.get(id=user_id)
                    # Find Employee by email
                    employee = Employee.objects.filter(email=django_user.username, is_active=True).first()
                    if not employee:
                        employee = Employee.objects.filter(email=django_user.email, is_active=True).first()
            except (User.DoesNotExist, InvalidToken, Exception) as e:
                import logging
                logger = logging.getLogger("dea_crm")
                logger.error(f"Error authenticating for reminder stream: {str(e)}")
        
        if not employee:
            employee = self._actor()
        
        if not employee:
            return Response(
                {'error': 'Authentication required. Provide JWT token via Authorization header or ?token query parameter.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        return sse_reminder_stream(request, employee.id)

    @extend_schema(
        summary="Snooze task reminder",
        description="Snooze a task reminder for a specified number of minutes. The reminder will be shown again after the snooze period.",
        tags=["Tasks"],
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'reminder_id': {'type': 'integer', 'description': 'ID of the reminder to snooze'},
                    'minutes': {'type': 'integer', 'description': 'Number of minutes to snooze (default: 10)', 'default': 10}
                },
                'required': ['reminder_id']
            }
        },
        responses={200: {'description': 'Reminder snoozed successfully'}},
    )
    @action(detail=False, methods=['post'], url_path='reminders/snooze')
    def snooze_reminder(self, request):
        """Snooze a task reminder"""
        from datetime import timedelta
        
        reminder_id = request.data.get('reminder_id')
        minutes = int(request.data.get('minutes', 10))
        
        if not reminder_id:
            return Response(
                {
                    'detail': 'reminder_id is required',
                    'reminder_id': None
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            reminder = TaskReminder.objects.get(id=reminder_id)
            
            # Verify the reminder belongs to a task assigned to the current user
            employee = self._actor()
            if not employee or reminder.task.assigned_to_id != employee.id:
                return Response(
                    {
                        'detail': 'You do not have permission to snooze this reminder',
                        'reminder_id': reminder_id
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Calculate new reminder time (add minutes to current time)
            new_remind_at = timezone.now() + timedelta(minutes=minutes)
            reminder.remind_at = new_remind_at
            reminder.is_sent = False  # Reset so it can be triggered again
            reminder.save(update_fields=['remind_at', 'is_sent'])
            
            # Create history entry
            TaskHistory.objects.create(
                task=reminder.task,
                action='reminder_change',
                changed_by=employee,
                changes={
                    'reminder': {
                        'action': 'snoozed',
                        'snoozed_until': new_remind_at.isoformat(),
                        'snooze_minutes': minutes
                    }
                }
            )
            
            return Response({
                'status': 'snoozed',
                'reminder_id': reminder.id,
                'remind_at': new_remind_at.isoformat(),
                'minutes': minutes,
                'message': f'Reminder {reminder.id} snoozed for {minutes} minutes'
            })
        except TaskReminder.DoesNotExist:
            return Response(
                {
                    'detail': 'Reminder not found',
                    'reminder_id': reminder_id if reminder_id else None
                },
                status=status.HTTP_404_NOT_FOUND
            )

    @extend_schema(
        summary="Dismiss task reminder",
        description="Dismiss a task reminder. The reminder will no longer be shown.",
        tags=["Tasks"],
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'reminder_id': {'type': 'integer', 'description': 'ID of the reminder to dismiss'}
                },
                'required': ['reminder_id']
            }
        },
        responses={200: {'description': 'Reminder dismissed successfully'}},
    )
    @action(detail=False, methods=['post'], url_path='reminders/dismiss')
    def dismiss_reminder(self, request):
        """Dismiss a task reminder"""
        reminder_id = request.data.get('reminder_id')
        
        if not reminder_id:
            return Response(
                {
                    'detail': 'reminder_id is required',
                    'reminder_id': None
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            reminder = TaskReminder.objects.get(id=reminder_id)
            
            # Verify the reminder belongs to a task assigned to the current user
            employee = self._actor()
            if not employee or reminder.task.assigned_to_id != employee.id:
                return Response(
                    {
                        'detail': 'You do not have permission to dismiss this reminder',
                        'reminder_id': reminder_id
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Mark as dismissed and sent
            reminder.is_sent = True
            reminder.save(update_fields=['is_sent'])
            
            # Create history entry
            TaskHistory.objects.create(
                task=reminder.task,
                action='reminder_change',
                changed_by=employee,
                changes={
                    'reminder': {
                        'action': 'dismissed',
                        'reminder_id': reminder.id
                    }
                }
            )
            
            return Response({
                'status': 'dismissed',
                'reminder_id': reminder.id,
                'message': f'Reminder {reminder.id} dismissed successfully'
            })
        except TaskReminder.DoesNotExist:
            return Response(
                {
                    'detail': 'Reminder not found',
                    'reminder_id': reminder_id if reminder_id else None
                },
                status=status.HTTP_404_NOT_FOUND
            )

    @extend_schema(
        summary="Check pending reminders",
        description="Check all pending reminders for the authenticated user. "
                    "Shows all reminders that haven't been sent yet (both due and future reminders).",
        tags=["Tasks"],
        responses={200: {'description': 'Pending reminders list'}},
    )
    @action(detail=False, methods=['get'], url_path='reminders/pending')
    def pending_reminders(self, request):
        """Check pending reminders for the current user (all future and due reminders)"""
        from task.models import TaskReminder
        
        employee = self._actor()
        if not employee:
            return Response(
                {'detail': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        now = timezone.now()
        
        # Find ALL pending reminders (both due and future)
        # Show ALL reminders regardless of task status - user can see what's pending
        # The scheduler will still only send reminders for active tasks
        pending_reminders = TaskReminder.objects.filter(
            task__assigned_to_id=employee.id,
            is_sent=False,  # Not sent yet
            task__is_deleted=False  # Don't show deleted tasks
            # Removed status filter - show all pending reminders
        ).select_related('task').order_by('remind_at')
        
        reminders_data = []
        for reminder in pending_reminders:
            task = reminder.task
            remind_at = reminder.remind_at
            is_due = remind_at <= now
            
            reminders_data.append({
                "reminder_id": reminder.id,
                "task_id": task.id,
                "task_title": task.title,
                "task_description": task.description or "",
                "remind_at": remind_at.isoformat(),
                "remind_at_formatted": remind_at.strftime("%Y-%m-%d %H:%M:%S"),
                "due_date": str(task.due_date),
                "due_time": str(task.due_time),
                "priority": task.priority,
                "task_status": task.status,
                "is_due": is_due,  # True if remind_at <= now, False if future
                "time_until_reminder": str(remind_at - now) if remind_at > now else "Due now",
                "will_trigger": task.status in ['to_do', 'in_progress', 'on_hold'] and not task.is_deleted  # Will scheduler send this?
            })
        
        return Response({
            'count': len(reminders_data),
            'current_time': now.isoformat(),
            'employee_id': employee.id,
            'reminders': reminders_data
        })