import json
from rest_framework import serializers
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from .models import Mail, MailAttachment
from task.models import Task
from task.serializers import TaskSerializer, TaskReminderSerializer
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.conf import settings
from employee.models import Employee
from .models import MailParticipantStatus
class MailAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MailAttachment
        fields = ['id', 'filename', 'content_type', 'file_size', 'uploaded_at']
        read_only_fields = fields


@extend_schema_field(OpenApiTypes.BOOL)
class ParticipantStatusBooleanField(serializers.Field):
    """
    Dual-purpose boolean field:
    - Uses serializer's getter (e.g., get_is_read) for representation
    - Accepts boolean input for write operations
    """
    def __init__(self, getter_name, **kwargs):
        self.getter_name = getter_name
        super().__init__(**kwargs)

    def get_attribute(self, instance):
        # Return the whole instance so the getter can access participant data
        return instance

    def to_representation(self, instance):
        getter = getattr(self.parent, self.getter_name)
        return getter(instance)

    def to_internal_value(self, data):
        if isinstance(data, bool):
            return data
        if isinstance(data, str):
            value = data.strip().lower()
            if value in {'true', '1', 'yes', 'on'}:
                return True
            if value in {'false', '0', 'no', 'off'}:
                return False
        raise serializers.ValidationError('This field must be a boolean.')

class MailSerializer(serializers.ModelSerializer):
    attachments = MailAttachmentSerializer(many=True, read_only=True)
    files = serializers.ListField(child=serializers.FileField(), write_only=True, required=False)
    sender_id = serializers.IntegerField(write_only=True, required=False)
    receiver_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_empty=True
    )
    sender = serializers.SerializerMethodField(read_only=True)
    receivers = serializers.SerializerMethodField(read_only=True)
    is_starred = ParticipantStatusBooleanField(getter_name='get_is_starred', required=False)
    is_read = ParticipantStatusBooleanField(getter_name='get_is_read', required=False)

    class Meta:
        model = Mail
        fields = [
            'id', 'from_email', 'to_emails', 'cc_emails', 'bcc_emails',
            'subject', 'body', 'direction', 'status', 'is_starred', 'scheduled_at',
            'attachments', 'files', 'created_at', 'updated_at',
            'sender_id', 'receiver_ids', 'sender', 'receivers', 'is_read'
        ]
        read_only_fields = ['created_at', 'updated_at', 'attachments', 'sender', 'receivers']

    def _resolve_context_employee_id(self, include_sender_fallback=False):
        request = self.context.get('request')
        if not request:
            return None

        employee_id = None
        if hasattr(request, 'query_params'):
            employee_id = request.query_params.get('employee_id')

        if not employee_id and hasattr(request, 'data'):
            employee_id = request.data.get('employee_id')
            if not employee_id and include_sender_fallback:
                employee_id = request.data.get('sender_id')

        if not employee_id and hasattr(request, 'user') and hasattr(request.user, 'id'):
            employee_id = request.user.id

        return employee_id

    def validate_to_emails(self, value):
        if not isinstance(value, list) or len(value) == 0:
            raise serializers.ValidationError('to_emails must be a non-empty list')
        validator = EmailValidator()
        errors = []
        for idx, email in enumerate(value):
            try:
                validator(email)
            except DjangoValidationError:
                errors.append({idx: f'Invalid email: {email}'})
        if errors:
            raise serializers.ValidationError(errors)
        return value

    def validate_cc_emails(self, value):
        if value in (None, ''):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError('cc_emails must be a list')
        validator = EmailValidator()
        for idx, email in enumerate(value):
            try:
                validator(email)
            except DjangoValidationError:
                raise serializers.ValidationError({idx: f'Invalid email: {email}'})
        return value

    def validate_bcc_emails(self, value):
        if value in (None, ''):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError('bcc_emails must be a list')
        validator = EmailValidator()
        for idx, email in enumerate(value):
            try:
                validator(email)
            except DjangoValidationError:
                raise serializers.ValidationError({idx: f'Invalid email: {email}'})
        return value

    def _coerce_email_list(self, data, key):
        if key not in data:
            return data
        val = data.get(key)
        if isinstance(val, list):
            return data
        if val in (None, ''):
            data[key] = []
            return data
        # Try JSON decode first
        if isinstance(val, str):
            try:
                decoded = json.loads(val)
                if isinstance(decoded, list):
                    data[key] = decoded
                    return data
            except Exception:
                pass
            # Fallback to comma/semicolon separated list
            parts = [p.strip() for p in val.replace(';', ',').split(',') if p.strip()]
            data[key] = parts
        return data

    def to_internal_value(self, data):
        # Normalize QueryDict (multipart/form-data) to primitives
        if hasattr(data, 'getlist'):
            keys = list(data.keys())
            normalized = {}
            list_like_keys = {'to_emails', 'cc_emails', 'bcc_emails', 'files', 'receiver_ids'}
            for k in keys:
                if k in list_like_keys:
                    vals = data.getlist(k)
                    normalized[k] = vals if len(vals) > 1 else (vals[0] if vals else [])
                else:
                    normalized[k] = data.get(k)
            mutable = normalized
        else:
            mutable = dict(data)

        # Empty strings to None for nullable fields
        if mutable.get('scheduled_at') == '':
            mutable['scheduled_at'] = None
        if mutable.get('linked_task') in ('', 'null', 'None'):
            mutable['linked_task'] = None
        if mutable.get('from_email') == '':
            mutable['from_email'] = None

        # Coerce potential string lists
        mutable = self._coerce_email_list(mutable, 'to_emails')
        mutable = self._coerce_email_list(mutable, 'cc_emails')
        mutable = self._coerce_email_list(mutable, 'bcc_emails')
        mutable = self._coerce_id_list(mutable, 'receiver_ids')

        # Normalize files: accept list, single file, or dict index->file; drop non-file values
        if 'files' in mutable:
            fval = mutable.get('files')
            files_list = []
            if isinstance(fval, dict):
                candidates = list(fval.values())
            elif isinstance(fval, list):
                candidates = fval
            else:
                candidates = [fval]
            for item in candidates:
                if isinstance(item, UploadedFile) or hasattr(item, 'read'):
                    files_list.append(item)
            mutable['files'] = files_list
        return super().to_internal_value(mutable)

    def to_representation(self, instance):
        """
        Convert empty string from_email to DEFAULT_FROM_EMAIL in response
        Shows the actual email address that will be used for sending
        """
        representation = super().to_representation(instance)
        from_email = representation.get('from_email')
        # If from_email is empty, null, or not provided, use DEFAULT_FROM_EMAIL
        if not from_email or from_email == '':
            representation['from_email'] = getattr(settings, 'DEFAULT_FROM_EMAIL', None)

        employee_id = self._resolve_context_employee_id(include_sender_fallback=True)

        if employee_id:
            if instance.receivers.filter(id=employee_id).exists():
                representation['direction'] = 'inbound'
            elif instance.sender_id and str(instance.sender_id) == str(employee_id):
                representation['direction'] = 'outbound'

        return representation

    def _employee_summary(self, employee):
        if not employee:
            return None
        return {
            'id': employee.id,
            'first_name': employee.first_name,
            'last_name': employee.last_name,
            'email': employee.email,
        }

    def get_sender(self, obj):
        return self._employee_summary(getattr(obj, 'sender', None))

    def get_receivers(self, obj):
        receivers = getattr(obj, 'receivers', None)
        if not receivers:
            return []
        return [self._employee_summary(employee) for employee in receivers.all()]

    def get_is_starred(self, obj):
        """Check if current employee has starred this mail"""
        employee_id = self._resolve_context_employee_id(include_sender_fallback=True)
        
        if employee_id:
            try:
                status = obj.participant_statuses.filter(employee_id=int(employee_id)).first()
                return status.is_starred if status else False
            except (ValueError, TypeError):
                pass
        return False

    def get_is_read(self, obj):
        """Check if current employee has read this mail"""
        employee_id = self._resolve_context_employee_id(include_sender_fallback=True)
        
        if employee_id:
            try:
                status = obj.participant_statuses.filter(employee_id=int(employee_id)).first()
                return status.is_read if status else False
            except (ValueError, TypeError):
                pass
        return False

    def _resolve_sender_id(self, validated_data):
        sender_id = validated_data.pop('sender_id', None)
        if not sender_id:
            raise serializers.ValidationError({'sender_id': 'sender_id is required.'})
        if not Employee.objects.filter(id=sender_id, is_deleted=False).exists():
            raise serializers.ValidationError({'sender_id': 'Sender not found.'})
        return sender_id

    def _resolve_receivers(self, receiver_ids):
        if not receiver_ids:
            return []
        employees = Employee.objects.filter(id__in=receiver_ids, is_deleted=False)
        found_ids = set(employees.values_list('id', flat=True))
        missing = [rid for rid in receiver_ids if rid not in found_ids]
        if missing:
            raise serializers.ValidationError({'receiver_ids': f"Receiver(s) not found: {missing}"})
        return list(found_ids)

    def create(self, validated_data):
        files = validated_data.pop('files', [])
        validated_data.pop('is_read', None)
        validated_data.pop('is_starred', None)
        receiver_ids = validated_data.pop('receiver_ids', None)
        sender_id = self._resolve_sender_id(validated_data)
        validated_data['sender_id'] = sender_id
        receivers = self._resolve_receivers(receiver_ids)

        self._ensure_from_email(validated_data)
        mail = Mail.objects.create(**validated_data)
        MailParticipantStatus.objects.get_or_create(
            mail=mail,
            employee_id=sender_id,
            defaults={'delete_status': 'sent', 'is_read': True, 'is_starred': False}
        )
        
        # Create default participant status for each receiver
        if receivers:
            mail.receivers.set(receivers)
            for receiver_id in receivers:
                MailParticipantStatus.objects.get_or_create(
                    mail=mail,
                    employee_id=receiver_id,
                    defaults={'delete_status': 'inbox', 'is_read': False, 'is_starred': False}
                )
        
        for f in files:
            MailAttachment.objects.create(mail=mail, file=f, filename=f.name)
        return mail

    def update(self, instance, validated_data):
        # Prevent sender changes through updates
        validated_data.pop('sender_id', None)

        receiver_ids = validated_data.pop('receiver_ids', None)
        # Handle is_read and is_starred updates via MailParticipantStatus
        is_read = validated_data.pop('is_read', None)
        is_starred = validated_data.pop('is_starred', None)
        
        # Get employee_id from request context (user, query params, or body)
        employee_id = self._resolve_context_employee_id(include_sender_fallback=False)
        
        # Update MailParticipantStatus if is_read or is_starred is provided
        if employee_id and (is_read is not None or is_starred is not None):
            try:
                employee = Employee.objects.get(id=int(employee_id), is_deleted=False)
                employee_id_int = employee.id
                participant_status, created = MailParticipantStatus.objects.get_or_create(
                    mail=instance,
                    employee=employee,
                    defaults={
                        'delete_status': 'inbox' if instance.receivers.filter(id=employee_id_int).exists() else 'sent',
                        'is_read': False,
                        'is_starred': False
                    }
                )
                
                update_fields = []
                if is_read is not None:
                    participant_status.is_read = is_read
                    update_fields.append('is_read')
                if is_starred is not None:
                    participant_status.is_starred = is_starred
                    update_fields.append('is_starred')
                
                if update_fields:
                    update_fields.append('updated_at')
                    participant_status.save(update_fields=update_fields)
            except (ValueError, TypeError, Employee.DoesNotExist):
                # If employee_id is invalid or employee not found, silently ignore
                # (don't break the update for other fields)
                pass

        self._ensure_from_email(validated_data)

        instance = super().update(instance, validated_data)
        if receiver_ids is not None:
            receivers = self._resolve_receivers(receiver_ids)
            instance.receivers.set(receivers)
        return instance

    def _ensure_from_email(self, validated_data):
        """
        Persist DEFAULT_FROM_EMAIL whenever payload omits from_email.
        """
        from_email = validated_data.get('from_email')
        if not from_email:
            default_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
            validated_data['from_email'] = default_email

    def _coerce_id_list(self, data, key):
        """
        Accept comma-separated or single values for receiver_ids.
        """
        if key not in data:
            return data
        value = data.get(key)
        if isinstance(value, list):
            numeric = []
            for item in value:
                try:
                    numeric.append(int(item))
                except (ValueError, TypeError):
                    continue
            data[key] = numeric
            return data
        if value in (None, ''):
            data[key] = []
            return data
        if isinstance(value, str):
            parts = [p.strip() for p in value.split(',') if p.strip()]
            numeric = []
            for p in parts:
                try:
                    numeric.append(int(p))
                except ValueError:
                    continue
            data[key] = numeric
        else:
            try:
                data[key] = [int(value)]
            except (ValueError, TypeError):
                data[key] = []
        return data


class CreateTaskFromMailSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    assigned_to = serializers.IntegerField(required=False, allow_null=True)
    due_date = serializers.DateField()
    due_time = serializers.TimeField(input_formats=['%H:%M', '%H:%M:%S', '%H:%M:%S.%f', '%H:%M:%S.%fZ', '%I:%M %p'])
    priority = serializers.ChoiceField(choices=[('low','Low'),('medium','Medium'),('high','High'),('urgent','Urgent')], default='medium')
    employee_id = serializers.IntegerField(required=True)
    reminders = TaskReminderSerializer(many=True, required=False)

    def to_internal_value(self, data):
        # Normalize QueryDict to plain dict and parse reminders
        if hasattr(data, 'getlist'):
            norm = {}
            for key in data.keys():
                vals = data.getlist(key)
                norm[key] = vals[0] if len(vals) == 1 else vals
            raw = norm.get('reminders')
        else:
            norm = data.copy() if hasattr(data, 'copy') else dict(data)
            raw = norm.get('reminders')

        # Treat empty or blank as no reminders
        if raw in (None, '', []):
            norm['reminders'] = []
        elif isinstance(raw, list) and all(isinstance(x, str) and x.strip() == '' for x in raw):
            norm['reminders'] = []
        elif isinstance(raw, str) and raw.strip():
            import json as _json
            try:
                parsed = _json.loads(raw)
                norm['reminders'] = [parsed] if isinstance(parsed, dict) else parsed
            except Exception:
                pass
        elif isinstance(raw, dict):
            norm['reminders'] = [raw]
        return super().to_internal_value(norm)

    def create(self, validated_data):
        # This serializer is not used to create itself
        raise NotImplementedError


