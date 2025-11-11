import json
from rest_framework import serializers
from .models import Mail, MailAttachment
from task.models import Task
from task.serializers import TaskSerializer, TaskReminderSerializer
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.conf import settings


class MailAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MailAttachment
        fields = ['id', 'filename', 'content_type', 'file_size', 'uploaded_at']
        read_only_fields = fields


class MailSerializer(serializers.ModelSerializer):
    attachments = MailAttachmentSerializer(many=True, read_only=True)
    files = serializers.ListField(child=serializers.FileField(), write_only=True, required=False)
    employee_id = serializers.IntegerField(write_only=True, required=True)
    # Temporarily hide linked_task from API responses

    class Meta:
        model = Mail
        fields = [
            'id', 'from_email', 'to_emails', 'cc_emails', 'bcc_emails',
            'subject', 'body', 'direction', 'status', 'scheduled_at',
            'attachments', 'files', 'created_at', 'updated_at', 'employee_id'
        ]
        read_only_fields = ['created_at', 'updated_at', 'attachments']

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
            list_like_keys = {'to_emails', 'cc_emails', 'bcc_emails', 'files'}
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
        if mutable.get('employee_id') == '':
            mutable['employee_id'] = None
        if mutable.get('from_email') == '':
            mutable['from_email'] = None

        # Coerce potential string lists
        mutable = self._coerce_email_list(mutable, 'to_emails')
        mutable = self._coerce_email_list(mutable, 'cc_emails')
        mutable = self._coerce_email_list(mutable, 'bcc_emails')

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
        return representation

    def create(self, validated_data):
        files = validated_data.pop('files', [])
        employee_id = validated_data.pop('employee_id')
        validated_data['owner_id'] = employee_id
        # Ensure from_email is None if empty string
        if validated_data.get('from_email') == '':
            validated_data['from_email'] = None
        mail = Mail.objects.create(**validated_data)
        for f in files:
            MailAttachment.objects.create(mail=mail, file=f, filename=f.name)
        return mail


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


