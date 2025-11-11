import logging
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from .models import Mail, MailAttachment
from .serializers import MailSerializer, CreateTaskFromMailSerializer
from task.models import Task, TaskAttachment, TaskHistory, TaskReminder
from notifications.signals import create_task_reminder_notification, create_task_assignment_notification
from task.serializers import TaskSerializer
from employee.models import Employee
from rest_framework.exceptions import ValidationError
logger = logging.getLogger(__name__)


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

    def _send_email(self, mail_instance):
        """
        Send email using Django's email backend.
        All emails are sent from DEFAULT_FROM_EMAIL configured in settings.
        Similar to forgot_password implementation.
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
        
        # Check email backend
        email_backend = getattr(settings, 'EMAIL_BACKEND', '')
        if 'console' in email_backend:
            logger.warning(f"Mail {mail_instance.id}: Using console email backend - email will be printed to console, not actually sent")
        
        # Prepare recipients
        recipients = mail_instance.to_emails if isinstance(mail_instance.to_emails, list) else [mail_instance.to_emails]
        cc_recipients = mail_instance.cc_emails if isinstance(mail_instance.cc_emails, list) else (mail_instance.cc_emails if mail_instance.cc_emails else [])
        bcc_recipients = mail_instance.bcc_emails if isinstance(mail_instance.bcc_emails, list) else (mail_instance.bcc_emails if mail_instance.bcc_emails else [])
        
        logger.info(f"Mail {mail_instance.id}: Attempting to send email from {from_email} to {recipients}")
        
        # Create email message
        email = EmailMultiAlternatives(
            subject=mail_instance.subject,
            body=mail_instance.body,
            from_email=from_email,
            to=recipients,
            cc=cc_recipients if cc_recipients else None,
            bcc=bcc_recipients if bcc_recipients else None,
        )
        
        # Attach files if any
        for attachment in mail_instance.attachments.all():
            if attachment.file:
                try:
                    attachment.file.open('rb')
                    email.attach(attachment.filename, attachment.file.read(), attachment.content_type)
                    attachment.file.close()
                    logger.info(f"Mail {mail_instance.id}: Attached file {attachment.filename}")
                except Exception as e:
                    logger.error(f"Mail {mail_instance.id}: Failed to attach {attachment.filename}: {e}")
        
        # Send email
        try:
            email.send(fail_silently=False)
            logger.info(f"Mail {mail_instance.id}: Email sent successfully to {recipients}")
            return True
        except Exception as e:
            logger.error(f"Mail {mail_instance.id}: Failed to send email: {e}", exc_info=True)
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


