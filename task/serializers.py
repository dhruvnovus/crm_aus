import json
import re
from rest_framework import serializers
from .models import Task, Subtask, TaskAttachment, TaskReminder, TaskHistory
from employee.models import Employee


class ChildTaskDetailSerializer(serializers.ModelSerializer):
    attachments = 'placeholder'
    reminders = 'placeholder'

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'assigned_to',
            'priority', 'status', 'due_date', 'due_time',
            'created_at', 'updated_at'
        ]


class SubtaskSerializer(serializers.ModelSerializer):
    child_title = serializers.CharField(source='child_task.title', read_only=True)
    child_status = serializers.CharField(source='child_task.status', read_only=True)
    child_task_details = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Subtask
        fields = ['id', 'child_task', 'child_title', 'child_status', 'child_task_details', 'sort_order']

    def to_internal_value(self, data):
        # Allow input as a bare integer task ID or as an object
        if isinstance(data, int):
            data = {'child_task': data}
        return super().to_internal_value(data)

    def get_child_task_details(self, obj):
        if obj.child_task_id and getattr(obj.child_task, 'is_deleted', False) is False:
            # Return full task details (excluding nested subtasks to avoid recursion)
            return ChildTaskDetailSerializer(obj.child_task).data
        return None


class TaskAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = TaskAttachment
        fields = ['id', 'file', 'filename', 'content_type', 'file_size', 'file_url', 'uploaded_at']
        read_only_fields = ['uploaded_at', 'file_size', 'file_url']
        
    def get_file_url(self, obj):
        """Return the URL to access the file"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


class TaskReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskReminder
        fields = ['id', 'remind_at', 'is_sent', 'created_at']
        read_only_fields = ['is_sent', 'created_at']


class TaskSerializer(serializers.ModelSerializer):
    subtasks = SubtaskSerializer(many=True, required=False)
    attachments = TaskAttachmentSerializer(many=True, required=False, read_only=True)
    files = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False,
        help_text='List of files to attach to this task'
    )
    reminders = TaskReminderSerializer(many=True, required=False)
    assigned_to_name = serializers.SerializerMethodField(read_only=True)
    # Accept multiple time formats including ISO with trailing 'Z' and 12-hour clock
    due_time = serializers.TimeField(
        input_formats=['%H:%M', '%H:%M:%S', '%H:%M:%S.%f', '%H:%M:%S.%fZ', '%I:%M %p']
    )

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'assigned_to', 'assigned_to_name',
            'priority', 'status', 'due_date', 'due_time', 'is_deleted',
            'created_at', 'updated_at', 'subtasks', 'attachments', 'files', 'reminders'
        ]
        read_only_fields = ['is_deleted', 'created_at', 'updated_at', 'assigned_to_name']

    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.full_name
        return None

    def to_representation(self, instance):
        """
        Ensure deleted child tasks are not included in the subtasks list.
        """
        rep = super().to_representation(instance)
        # Replace subtasks with only non-deleted child tasks
        try:
            queryset = instance.subtasks.select_related('child_task').filter(child_task__is_deleted=False).order_by('sort_order', 'id')
            rep['subtasks'] = SubtaskSerializer(queryset, many=True, context=self.context).data
        except Exception:
            # Fallback to whatever was already serialized
            pass
        return rep
    def to_internal_value(self, data):
        """
        Parse JSON strings from multipart/form-data for nested fields.
        When using multipart/form-data, nested JSON structures come as strings.
        """
        # Handle QueryDict (from multipart/form-data) or regular dict
        if hasattr(data, 'getlist'):
            # QueryDict - convert to regular dict, handling multiple values
            data_dict = {}
            for key in data.keys():
                value = data.getlist(key)
                if len(value) == 1:
                    data_dict[key] = value[0]
                else:
                    data_dict[key] = value
        else:
            # Regular dict - create a copy
            data_dict = data.copy() if hasattr(data, 'copy') else dict(data)
        
        # Parse bracket notation for subtasks (e.g., subtasks[0][child_task])
        subtasks_list = []
        subtask_keys = [k for k in data_dict.keys() if k.startswith('subtasks[')]
        if subtask_keys:
            # Group by index
            subtask_dict = {}
            for key in subtask_keys:
                match = re.match(r'subtasks\[(\d+)\]\[(\w+)\]', key)
                if match:
                    index = int(match.group(1))
                    field = match.group(2)
                    if index not in subtask_dict:
                        subtask_dict[index] = {}
                    subtask_dict[index][field] = data_dict[key]
                    # Remove from data_dict to avoid duplicate processing
                    del data_dict[key]
            
            # Convert to list format
            if subtask_dict:
                for index in sorted(subtask_dict.keys()):
                    subtask_item = subtask_dict[index]
                    # Convert sort_order to int if present, default to index
                    if 'sort_order' in subtask_item:
                        try:
                            sort_order = int(subtask_item['sort_order'])
                            # Handle invalid sort_order values
                            if sort_order < 0 or sort_order > 10000:
                                sort_order = index
                            subtask_item['sort_order'] = sort_order
                        except (ValueError, TypeError):
                            subtask_item['sort_order'] = index
                    else:
                        subtask_item['sort_order'] = index
                    subtasks_list.append(subtask_item)
                data_dict['subtasks'] = subtasks_list
        
        # Parse subtasks if provided as JSON string; gracefully handle empty strings from multipart forms
        elif 'subtasks' in data_dict:
            subtasks_value = data_dict.get('subtasks')
            if isinstance(subtasks_value, str):
                stripped = subtasks_value.strip()
                # Treat empty strings or explicit nulls as no subtasks
                if stripped == '' or stripped.lower() in ('null', 'none'):
                    data_dict['subtasks'] = []
                else:
                    try:
                        parsed = json.loads(stripped)
                        # Ensure it's a list
                        if isinstance(parsed, list):
                            data_dict['subtasks'] = parsed
                        elif isinstance(parsed, dict):
                            # Single object, wrap in list
                            data_dict['subtasks'] = [parsed]
                        else:
                            # Invalid format, raise clear error
                            raise serializers.ValidationError({
                                'subtasks': f'Invalid format. Expected JSON array like [{{"child_task": 10, "sort_order": 0}}], but got: {stripped[:50]}...'
                            })
                    except json.JSONDecodeError as e:
                        # Invalid JSON, provide helpful error
                        raise serializers.ValidationError({
                            'subtasks': f'Invalid JSON format. Please use valid JSON array format: [{{"child_task": 10, "sort_order": 0}}]. Error: {str(e)}'
                        })
                    except Exception as e:
                        # Other errors
                        raise serializers.ValidationError({
                            'subtasks': f'Error parsing subtasks: {str(e)}'
                        })
        
        # Parse bracket notation for reminders (e.g., reminders[0][remind_at])
        reminders_list = []
        reminder_keys = [k for k in data_dict.keys() if k.startswith('reminders[')]
        if reminder_keys:
            # Group by index
            reminder_dict = {}
            for key in reminder_keys:
                match = re.match(r'reminders\[(\d+)\]\[(\w+)\]', key)
                if match:
                    index = int(match.group(1))
                    field = match.group(2)
                    if index not in reminder_dict:
                        reminder_dict[index] = {}
                    reminder_dict[index][field] = data_dict[key]
                    # Remove from data_dict to avoid duplicate processing
                    del data_dict[key]
            
            # Convert to list format
            if reminder_dict:
                for index in sorted(reminder_dict.keys()):
                    reminders_list.append(reminder_dict[index])
                data_dict['reminders'] = reminders_list
        
        # Parse reminders if it's a string (JSON)
        elif 'reminders' in data_dict:
            reminders_value = data_dict.get('reminders')
            if isinstance(reminders_value, str):
                try:
                    parsed = json.loads(reminders_value)
                    # If it's a single dict, wrap it in a list
                    if isinstance(parsed, dict):
                        data_dict['reminders'] = [parsed]
                    else:
                        data_dict['reminders'] = parsed
                except (json.JSONDecodeError, TypeError):
                    # If parsing fails, pass it through and let the serializer handle validation
                    pass
            elif isinstance(reminders_value, dict):
                # If it's already a dict (not a string), wrap it in a list
                data_dict['reminders'] = [reminders_value]
        
        # Remove 'files' from data_dict to avoid validation issues
        # Files will be handled separately from request.FILES in the view
        if 'files' in data_dict:
            del data_dict['files']
        
        return super().to_internal_value(data_dict)

    def create(self, validated_data):
        subtasks_data = validated_data.pop('subtasks', [])
        files_data = validated_data.pop('files', None)  # Will be passed from view
        reminders_data = validated_data.pop('reminders', [])
        task = Task.objects.create(**validated_data)
        
        # Create subtasks
        if subtasks_data:
            normalized = self._normalize_subtasks(subtasks_data, task.id)
            for index, st in enumerate(normalized):
                Subtask.objects.create(parent_task=task, child_task_id=st['child_task_id'], sort_order=st.get('sort_order', index))
        
        # Create attachments from uploaded files (passed from view via context)
        files_data = getattr(self, 'context', {}).get('files', [])
        if files_data:
            for uploaded_file in files_data:
                TaskAttachment.objects.create(
                    task=task,
                    file=uploaded_file,
                    filename=uploaded_file.name
                )
        
        # Create reminders
        if reminders_data:
            for rm in reminders_data:
                TaskReminder.objects.create(task=task, **rm)
        
        # Refresh from database to get related objects
        task.refresh_from_db()
        return task

    def update(self, instance, validated_data):
        subtasks_data = validated_data.pop('subtasks', None)
        reminders_data = validated_data.pop('reminders', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if subtasks_data is not None:
            instance.subtasks.all().delete()
            normalized = self._normalize_subtasks(subtasks_data, instance.id)
            for index, st in enumerate(normalized):
                Subtask.objects.create(parent_task=instance, child_task_id=st['child_task_id'], sort_order=st.get('sort_order', index))

        # Add new attachments from uploaded files (passed from view via context)
        files_data = getattr(self, 'context', {}).get('files', None)
        if files_data is not None:
            for uploaded_file in files_data:
                TaskAttachment.objects.create(
                    task=instance,
                    file=uploaded_file,
                    filename=uploaded_file.name
                )

        if reminders_data is not None:
            instance.reminders.all().delete()
            for rm in reminders_data:
                TaskReminder.objects.create(task=instance, **rm)

        return instance

    def _normalize_subtasks(self, subtasks_data, parent_task_id):
        normalized = []
        seen = set()
        for index, st in enumerate(subtasks_data):
            if isinstance(st, int):
                child_id = st
                sort_order = index
            else:
                child_id = st.get('child_task')
                sort_order = st.get('sort_order', index)

            # If the nested serializer already converted to a Task instance, extract id
            if hasattr(child_id, 'id'):
                child_id = child_id.id
            if not child_id:
                raise serializers.ValidationError({'subtasks': f'Item {index} missing child_task id'})
            if int(child_id) == int(parent_task_id):
                raise serializers.ValidationError({'subtasks': 'A task cannot be a subtask of itself'})
            if child_id in seen:
                raise serializers.ValidationError({'subtasks': 'Duplicate child_task ids are not allowed'})

            # Ensure referenced task exists
            if not Task.objects.filter(id=child_id, is_deleted=False).exists():
                raise serializers.ValidationError({'subtasks': f'Referenced task {child_id} does not exist'})

            normalized.append({'child_task_id': child_id, 'sort_order': sort_order})
            seen.add(child_id)
        return normalized


class TaskHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = TaskHistory
        fields = ['id', 'action', 'changed_by', 'changed_by_name', 'changes', 'note', 'timestamp']
        read_only_fields = ['timestamp', 'changed_by_name']

    def get_changed_by_name(self, obj):
        if obj.changed_by:
            return obj.changed_by.full_name
        return None


