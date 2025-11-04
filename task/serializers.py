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
        if obj.child_task_id:
            # Return full task details (excluding nested subtasks to avoid recursion)
            return ChildTaskDetailSerializer(obj.child_task).data
        return None


class TaskAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskAttachment
        fields = ['id', 'filename', 'content_type', 'data_base64', 'uploaded_at']
        read_only_fields = ['uploaded_at']


class TaskReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskReminder
        fields = ['id', 'remind_at', 'is_sent', 'created_at']
        read_only_fields = ['is_sent', 'created_at']


class TaskSerializer(serializers.ModelSerializer):
    subtasks = SubtaskSerializer(many=True, required=False)
    attachments = TaskAttachmentSerializer(many=True, required=False)
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
            'created_at', 'updated_at', 'subtasks', 'attachments', 'reminders'
        ]
        read_only_fields = ['is_deleted', 'created_at', 'updated_at', 'assigned_to_name']

    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.full_name
        return None

    def create(self, validated_data):
        subtasks_data = validated_data.pop('subtasks', [])
        attachments_data = validated_data.pop('attachments', [])
        reminders_data = validated_data.pop('reminders', [])
        task = Task.objects.create(**validated_data)
        normalized = self._normalize_subtasks(subtasks_data, task.id)
        for index, st in enumerate(normalized):
            Subtask.objects.create(parent_task=task, child_task_id=st['child_task_id'], sort_order=st.get('sort_order', index))
        for at in attachments_data:
            TaskAttachment.objects.create(task=task, **at)
        for rm in reminders_data:
            TaskReminder.objects.create(task=task, **rm)
        return task

    def update(self, instance, validated_data):
        subtasks_data = validated_data.pop('subtasks', None)
        attachments_data = validated_data.pop('attachments', None)
        reminders_data = validated_data.pop('reminders', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if subtasks_data is not None:
            instance.subtasks.all().delete()
            normalized = self._normalize_subtasks(subtasks_data, instance.id)
            for index, st in enumerate(normalized):
                Subtask.objects.create(parent_task=instance, child_task_id=st['child_task_id'], sort_order=st.get('sort_order', index))

        if attachments_data is not None:
            instance.attachments.all().delete()
            for at in attachments_data:
                TaskAttachment.objects.create(task=instance, **at)

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


