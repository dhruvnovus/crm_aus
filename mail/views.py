import logging
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django.conf import settings
from django.utils import timezone
from django.utils.html import strip_tags
from django.http import FileResponse, Http404
from .models import Mail, MailAttachment, MailParticipantStatus
from .serializers import MailSerializer, CreateTaskFromMailSerializer
from .email_service import send_email_via_smtp2go
from task.models import Task, TaskAttachment, TaskHistory, TaskReminder
from notifications.signals import create_task_reminder_notification, create_task_assignment_notification
from task.serializers import TaskSerializer
from employee.models import Employee
from rest_framework.exceptions import ValidationError
from django.db.models import Q
logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        summary="List mails",
        tags=["Mails"],
        parameters=[
            OpenApiParameter(name='employee_id', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=True, description='Owner employee id'),
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by mail status (draft, sent, scheduled). Use 'trash' for trash view or 'starred' to list starred mails."
            ),
            OpenApiParameter(name='direction', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, required=False, description="Filter by direction (inbound/outbound)"),
            OpenApiParameter(name='is_starred', type=OpenApiTypes.BOOL, location=OpenApiParameter.QUERY, required=False, description="Filter starred mails explicitly"),
            OpenApiParameter(name='is_read', type=OpenApiTypes.BOOL, location=OpenApiParameter.QUERY, required=False, description="Filter mails by read status"),
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
    update=extend_schema(
        summary="Update mail (full)",
        tags=["Mails"],
        request=MailSerializer,
        parameters=[
            OpenApiParameter(
                name='employee_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description='update'
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Update mail (partial)",
        tags=["Mails"],
        request=MailSerializer,
        parameters=[
            OpenApiParameter(
                name='employee_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description='update'
            ),
        ],
    ),
    destroy=extend_schema(
        summary="Delete mail",
        description="Delete mail for the current participant. First delete moves to trash, second delete removes.",
        tags=["Mails"],
        parameters=[
            OpenApiParameter(name='employee_id', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=True, description='Employee ID of the participant deleting the mail'),
        ],
    ),
)
class MailViewSet(viewsets.ModelViewSet):
    queryset = Mail.objects.select_related(
        'linked_task',
        'linked_task__assigned_to',
        'sender',
    ).prefetch_related('receivers').all()
    serializer_class = MailSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = []
    search_fields = ['subject', 'body', 'from_email']
    ordering_fields = ['created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        employee_id = self.request.query_params.get('employee_id')
        status = self.request.query_params.get('status')
        direction = self.request.query_params.get('direction')
        is_starred = self.request.query_params.get('is_starred')
        is_read = self.request.query_params.get('is_read')

        # Skip employee_id requirement for download_attachment action
        # Authentication and permissions are handled by get_object() and the action itself
        if self.request.method in ['GET', 'HEAD', 'OPTIONS'] and self.action != 'download_attachment':
            if not employee_id:
                raise ValidationError({'employee_id': 'This query parameter is required.'})
            try:
                employee_id_int = int(employee_id)
            except (TypeError, ValueError):
                raise ValidationError({'employee_id': 'Invalid employee_id'})

            qs = self._apply_participant_filter(qs, employee_id, direction)
            qs = qs.exclude(~Q(sender_id=employee_id_int) & Q(status='draft'))

            # Filter by status flag supplied by the client
            if status == 'starred':
                # Filter mails starred by the current employee
                qs = qs.filter(participant_statuses__employee_id=employee_id, participant_statuses__is_starred=True).distinct()
            elif status not in (None, '', 'trash'):
                qs = qs.filter(status=status)

            if direction and direction not in {'inbound', 'outbound'}:
                qs = qs.filter(direction=direction)

            if is_starred not in (None, ''):
                # Filter by whether current employee has starred
                if self._coerce_bool(is_starred):
                    qs = qs.filter(participant_statuses__employee_id=employee_id, participant_statuses__is_starred=True).distinct()
                else:
                    qs = qs.exclude(participant_statuses__employee_id=employee_id, participant_statuses__is_starred=True)

            if is_read not in (None, ''):
                # Filter by whether current employee has read
                if self._coerce_bool(is_read):
                    qs = qs.filter(participant_statuses__employee_id=employee_id, participant_statuses__is_read=True).distinct()
                else:
                    qs = qs.exclude(participant_statuses__employee_id=employee_id, participant_statuses__is_read=True)

            qs = self._apply_visibility_filters(
                qs,
                employee_id,
                direction_param=direction,
                viewing_trash=(status == 'trash')
            )

        return qs

    @staticmethod
    def _coerce_bool(value):
        if isinstance(value, bool):
            return value
        return str(value).lower() in {'true', '1', 'yes', 'on'}

    def _apply_participant_filter(self, queryset, employee_id, direction_param):
        """
        Use sender/receiver pairing to decide which mails to show.
        - direction=inbound => receivers include employee
        - direction=outbound => sender_id matches employee
        - otherwise => either sender or receiver matches
        """
        if direction_param == 'inbound':
            return queryset.filter(receivers__id=employee_id)
        if direction_param == 'outbound':
            return queryset.filter(sender_id=employee_id)

        qs = queryset.filter(Q(sender_id=employee_id) | Q(receivers__id=employee_id)).distinct()

        if direction_param not in (None, ''):
            qs = qs.filter(direction=direction_param)

        return qs

    def destroy(self, request, *args, **kwargs):
        employee_id = request.query_params.get('employee_id') or request.data.get('employee_id')
        if not employee_id:
            raise ValidationError({'employee_id': 'This query parameter is required.'})
        instance = self.get_object()
        self._soft_delete(instance, employee_id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _actor(self):
        """Get authenticated Employee from request user"""
        user = getattr(self.request, 'user', None)
        if not user:
            return None
        
        # If user is already an Employee instance, return it
        if isinstance(user, Employee):
            return user
        
        # Try to get Employee by email (since User.username is email)
        if hasattr(user, 'email'):
            employee = Employee.objects.filter(email=user.email, is_active=True).first()
            if employee:
                return employee
        elif hasattr(user, 'username'):
            employee = Employee.objects.filter(email=user.username, is_active=True).first()
            if employee:
                return employee
        
        # Fallback: try direct ID match (in case Employee ID matches User ID)
        if hasattr(user, 'id'):
            employee = Employee.objects.filter(id=user.id, is_active=True).first()
            if employee:
                return employee
        
        return None

    def _send_email(self, mail_instance): 
        """
        Send email using SMTP2GO API.
        All emails are sent from DEFAULT_FROM_EMAIL configured in settings.
        """
        if not mail_instance.to_emails:
            logger.warning(f"Mail {mail_instance.id}: Cannot send email - to_emails is empty")
            return False
        
        if mail_instance.direction != 'outbound':
            logger.warning(f"Mail {mail_instance.id}: Cannot send email - direction is not outbound")
            return False
        
        # Use DEFAULT_FROM_EMAIL from settings - all emails appear from this address
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        if not from_email:
            logger.error(f"Mail {mail_instance.id}: Cannot send email - DEFAULT_FROM_EMAIL is not configured in settings")
            return False
        
        # Prepare recipients
        recipients = mail_instance.to_emails if isinstance(mail_instance.to_emails, list) else [mail_instance.to_emails]
        cc_recipients = mail_instance.cc_emails if isinstance(mail_instance.cc_emails, list) else (mail_instance.cc_emails if mail_instance.cc_emails else [])
        bcc_recipients = mail_instance.bcc_emails if isinstance(mail_instance.bcc_emails, list) else (mail_instance.bcc_emails if mail_instance.bcc_emails else [])
        
        logger.info(f"Mail {mail_instance.id}: Attempting to send email via SMTP2GO from {from_email} to {recipients}")
        
        # Prepare attachments for SMTP2GO
        attachments = []
        for attachment in mail_instance.attachments.all():
            if attachment.file:
                try:
                    attachment.file.open('rb')
                    file_content = attachment.file.read()
                    attachment.file.close()
                    
                    attachments.append({
                        'filename': attachment.filename,
                        'content': file_content,
                        'content_type': attachment.content_type or 'application/octet-stream'
                    })
                    logger.info(f"Mail {mail_instance.id}: Prepared attachment {attachment.filename}")
                except Exception as e:
                    logger.error(f"Mail {mail_instance.id}: Failed to read attachment {attachment.filename}: {e}")
        
        # Send email via SMTP2GO
        plain_text_body = strip_tags(mail_instance.body or '')

        result = send_email_via_smtp2go(
            to_emails=recipients,
            subject=mail_instance.subject,
            text_body=plain_text_body or mail_instance.body or '',
            sender_email=from_email,
            cc_emails=cc_recipients if cc_recipients else None,
            bcc_emails=bcc_recipients if bcc_recipients else None,
            html_body=mail_instance.body,
            attachments=attachments if attachments else None
        )
        
        if result.get('success'):
            logger.info(f"Mail {mail_instance.id}: Email sent successfully via SMTP2GO to {recipients}")
            return True
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"Mail {mail_instance.id}: Failed to send email via SMTP2GO: {error_msg}")
            return False

    def update(self, request, *args, **kwargs):
        """
        Update mail - send email if status changes to 'sent'
        Email sending happens in background and doesn't affect API response
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # Store previous status to detect changes
        previous_status = instance.status
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated_instance = serializer.save()
        
        # Send email if status changed to 'sent' and it's an outbound email
        # Errors in email sending are caught and logged, but don't affect the API response
        if (previous_status != 'sent' and updated_instance.status == 'sent' and 
            updated_instance.direction == 'outbound'):
            try:
                self._send_email(updated_instance)
            except Exception:
                # Email sending failed, but don't break the API response
                # The mail record is still updated successfully
                pass
        
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        """
        Partially update mail - send email if status changes to 'sent'
        """
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """
        Create mail - send email if status is 'sent'
        Email sending happens in background and doesn't affect API response
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mail_instance = serializer.save()
        
        # Send email if status is 'sent' and it's an outbound email
        # Errors in email sending are caught and logged, but don't affect the API response
        if mail_instance.status == 'sent' and mail_instance.direction == 'outbound':
            logger.info(f"Mail {mail_instance.id}: Created with status 'sent', attempting to send email")
            try:
                result = self._send_email(mail_instance)
                if not result:
                    logger.warning(f"Mail {mail_instance.id}: Email sending returned False - check logs above for details")
            except Exception as e:
                # Email sending failed, but don't break the API response
                # The mail record is still saved successfully
                logger.error(f"Mail {mail_instance.id}: Exception during email sending: {e}", exc_info=True)
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(summary="Create task from mail", tags=["Mails"], request=CreateTaskFromMailSerializer)
    @action(detail=True, methods=['post'])
    def create_task(self, request, pk=None):
        mail = self.get_object()
        serializer = CreateTaskFromMailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        # ensure mail belongs to the same employee
        employee_id = str(data['employee_id'])
        sender_match = mail.sender_id and str(mail.sender_id) == employee_id
        receiver_match = mail.receivers.filter(id=employee_id).exists()
        if not (sender_match or receiver_match):
            return Response({'detail': 'employee_id does not match mail participant.'}, status=status.HTTP_400_BAD_REQUEST)

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

    def _apply_visibility_filters(self, queryset, employee_id, direction_param=None, viewing_trash=False):
        """
        Hide mails that a participant has deleted from their views.
        Uses MailParticipantStatus.delete_status field:
        - 'sent'/'inbox': visible in normal view
        - 'trash': visible only in trash view
        - 'deleted': permanently hidden
        """
        try:
            employee_id = int(employee_id)
        except (TypeError, ValueError):
            raise ValidationError({'employee_id': 'Invalid employee_id'})

        if viewing_trash:
            qs = queryset.filter(
                participant_statuses__employee_id=employee_id,
                participant_statuses__delete_status='trash'
            ).distinct()
        else:
            deleted_ids = queryset.filter(
                participant_statuses__employee_id=employee_id,
                participant_statuses__delete_status__in=['deleted', 'trash']
            ).values_list('id', flat=True)
            qs = queryset.exclude(id__in=list(deleted_ids))

        if direction_param == 'inbound':
            return qs.filter(receivers__id=employee_id).distinct()
        if direction_param == 'outbound':
            return qs.filter(sender_id=employee_id).distinct()

        return qs

    def _soft_delete(self, mail_instance, employee_id):
        """
        Toggle delete status for sender/receiver instead of removing the record globally.
        Uses MailParticipantStatus.delete_status field to track per-participant delete status.
        Flow:
        1. First delete: 'sent'/'inbox' -> 'trash' (mail moves to trash)
        2. Delete from trash: 'trash' -> 'deleted' (mail permanently hidden for that participant)
        """
        try:
            employee_id = int(employee_id)
        except (TypeError, ValueError):
            raise ValidationError({'employee_id': 'Invalid employee_id'})

        try:
            employee = Employee.objects.get(id=employee_id, is_deleted=False)
        except Employee.DoesNotExist:
            raise ValidationError({'employee_id': 'Employee not found.'})

        # Check if employee is sender or receiver
        is_sender = mail_instance.sender_id == employee_id
        is_receiver = mail_instance.receivers.filter(id=employee_id).exists()

        if not (is_sender or is_receiver):
            raise ValidationError({'employee_id': 'Employee is not a participant in this mail.'})

        # Get or create participant status with default based on role
        default_status = 'sent' if is_sender else 'inbox'
        participant_status, created = MailParticipantStatus.objects.get_or_create(
            mail=mail_instance,
            employee=employee,
            defaults={'delete_status': default_status, 'is_read': False, 'is_starred': False}
        )

        current_status = participant_status.delete_status

        # Delete flow logic
        if current_status in ('sent', 'inbox'):
            # First delete: move to trash
            participant_status.delete_status = 'trash'
            participant_status.save(update_fields=['delete_status', 'updated_at'])
        elif current_status == 'trash':
            # Delete from trash: permanently hide
            participant_status.delete_status = 'deleted'
            participant_status.save(update_fields=['delete_status', 'updated_at'])

    # @extend_schema(summary="Mark mail as read", tags=["Mails"])
    # @action(detail=True, methods=['post'])
    # def mark_read(self, request, pk=None):
    #     """Mark mail as read for the current employee"""
    #     mail = self.get_object()
    #     employee_id = request.query_params.get('employee_id') or request.data.get('employee_id')
    #     if not employee_id:
    #         return Response({'error': 'employee_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
    #     try:
    #         employee = Employee.objects.get(id=employee_id, is_deleted=False)
    #     except Employee.DoesNotExist:
    #         return Response({'error': 'Employee not found'}, status=status.HTTP_404_NOT_FOUND)
        
    #     # Check if employee is sender or receiver
    #     if mail.sender_id != int(employee_id) and not mail.receivers.filter(id=employee_id).exists():
    #         return Response({'error': 'Employee is not a participant in this mail'}, status=status.HTTP_403_FORBIDDEN)
        
    #     # Get or create participant status
    #     status_obj, created = MailParticipantStatus.objects.get_or_create(
    #         mail=mail,
    #         employee=employee,
    #         defaults={'is_read': True, 'read_at': timezone.now()}
    #     )
    #     if not created:
    #         status_obj.is_read = True
    #         status_obj.read_at = timezone.now()
    #         status_obj.save(update_fields=['is_read', 'read_at', 'updated_at'])
        
    #     serializer = self.get_serializer(mail, context={'request': request})
    #     return Response(serializer.data)

    # @extend_schema(summary="Mark mail as unread", tags=["Mails"])
    # @action(detail=True, methods=['post'])
    # def mark_unread(self, request, pk=None):
    #     """Mark mail as unread for the current employee"""
    #     mail = self.get_object()
    #     employee_id = request.query_params.get('employee_id') or request.data.get('employee_id')
    #     if not employee_id:
    #         return Response({'error': 'employee_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
    #     try:
    #         employee = Employee.objects.get(id=employee_id, is_deleted=False)
    #     except Employee.DoesNotExist:
    #         return Response({'error': 'Employee not found'}, status=status.HTTP_404_NOT_FOUND)
        
    #     MailParticipantStatus.objects.filter(mail=mail, employee=employee).update(
    #         is_read=False,
    #         read_at=None,
    #         updated_at=timezone.now()
    #     )
    #     serializer = self.get_serializer(mail, context={'request': request})
    #     return Response(serializer.data)

    # @extend_schema(summary="Star mail", tags=["Mails"])
    # @action(detail=True, methods=['post'])
    # def star(self, request, pk=None):
    #     """Star mail for the current employee"""
    #     mail = self.get_object()
    #     employee_id = request.query_params.get('employee_id') or request.data.get('employee_id')
    #     if not employee_id:
    #         return Response({'error': 'employee_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
    #     try:
    #         employee = Employee.objects.get(id=employee_id, is_deleted=False)
    #     except Employee.DoesNotExist:
    #         return Response({'error': 'Employee not found'}, status=status.HTTP_404_NOT_FOUND)
        
    #     # Check if employee is sender or receiver
    #     if mail.sender_id != int(employee_id) and not mail.receivers.filter(id=employee_id).exists():
    #         return Response({'error': 'Employee is not a participant in this mail'}, status=status.HTTP_403_FORBIDDEN)
        
    #     # Get or create participant status
    #     status_obj, created = MailParticipantStatus.objects.get_or_create(
    #         mail=mail,
    #         employee=employee,
    #         defaults={'is_starred': True, 'starred_at': timezone.now()}
    #     )
    #     if not created:
    #         status_obj.is_starred = True
    #         status_obj.starred_at = timezone.now()
    #         status_obj.save(update_fields=['is_starred', 'starred_at', 'updated_at'])
        
    #     serializer = self.get_serializer(mail, context={'request': request})
    #     return Response(serializer.data)

    # @extend_schema(summary="Unstar mail", tags=["Mails"])
    # @action(detail=True, methods=['post'])
    # def unstar(self, request, pk=None):
    #     """Unstar mail for the current employee"""
    #     mail = self.get_object()
    #     employee_id = request.query_params.get('employee_id') or request.data.get('employee_id')
    #     if not employee_id:
    #         return Response({'error': 'employee_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
    #     try:
    #         employee = Employee.objects.get(id=employee_id, is_deleted=False)
    #     except Employee.DoesNotExist:
    #         return Response({'error': 'Employee not found'}, status=status.HTTP_404_NOT_FOUND)
        
    #     MailParticipantStatus.objects.filter(mail=mail, employee=employee).update(
    #         is_starred=False,
    #         starred_at=None,
    #         updated_at=timezone.now()
    #     )
    #     serializer = self.get_serializer(mail, context={'request': request})
    #     return Response(serializer.data)

    @extend_schema(
        summary="Download mail attachment",
        description="Download a specific attachment file from a mail",
        tags=["Mails"],
        responses={200: OpenApiTypes.BINARY},
    )
    @action(detail=True, methods=['get'], url_path='attachments/(?P<attachment_id>[^/.]+)/download')
    def download_attachment(self, request, pk=None, attachment_id=None):
        """Download a specific attachment file from a mail"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            mail = self.get_object()
        except Exception as e:
            logger.error(f"Error getting mail object: {str(e)}", exc_info=True)
            return Response(
                {'detail': 'Mail not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verify user has access to this mail
        # Access is granted if user is:
        # 1. The sender
        # 2. In the receivers (ManyToMany)
        # 3. Their email is in to_emails, cc_emails, or bcc_emails
        authenticated_employee = self._actor()
        if not authenticated_employee:
            return Response(
                {'detail': 'Authentication required.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        has_access = False
        user_email = authenticated_employee.email.lower() if authenticated_employee.email else None
        
        # Check if user is sender
        if mail.sender_id == authenticated_employee.id:
            has_access = True
        
        # Check if user is in receivers (ManyToMany)
        if not has_access:
            has_access = mail.receivers.filter(id=authenticated_employee.id).exists()
        
        # Check if user's email is in to_emails, cc_emails, or bcc_emails
        if not has_access and user_email:
            to_emails = [e.lower() for e in (mail.to_emails or []) if isinstance(e, str)]
            cc_emails = [e.lower() for e in (mail.cc_emails or []) if isinstance(e, str)]
            bcc_emails = [e.lower() for e in (mail.bcc_emails or []) if isinstance(e, str)]
            
            has_access = (
                user_email in to_emails or
                user_email in cc_emails or
                user_email in bcc_emails
            )
        
        if not has_access:
            return Response(
                {'detail': 'You do not have permission to access this mail.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            attachment = MailAttachment.objects.get(id=attachment_id, mail=mail)
            if not attachment.file:
                raise Http404("File not found")
            
            # Open file and create response
            file_handle = attachment.file.open()
            response = FileResponse(
                file_handle,
                content_type=attachment.content_type or 'application/octet-stream'
            )
            response['Content-Disposition'] = f'attachment; filename="{attachment.filename}"'
            return response
        except MailAttachment.DoesNotExist:
            raise Http404("Attachment not found")
        except Exception as e:
            logger.error(f"Error downloading attachment {attachment_id}: {str(e)}", exc_info=True)
            return Response(
                {'detail': f'Error downloading attachment: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )