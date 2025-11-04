from django.utils import timezone
from django.db.models import Q
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db import transaction, IntegrityError
from .models import Task, TaskHistory
from employee.models import Employee
from .serializers import TaskSerializer, TaskHistorySerializer


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.filter(is_deleted=False)
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]
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
                task = serializer.save()
        except (IntegrityError, ValueError) as exc:
            raise ValidationError({'detail': str(exc)})
        changes = {}
        if prev_values['assigned_to'] != task.assigned_to_id:
            changes['assigned_to'] = {'from': prev_values['assigned_to'], 'to': task.assigned_to_id}
            action = 'assign'
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

    @action(detail=True, methods=['get', 'post'])
    def history(self, request, pk=None):
        task = self.get_object()
        if request.method.lower() == 'post':
            note = request.data.get('note', '')
            entry = TaskHistory.objects.create(task=task, action='comment', note=note, changed_by=self._actor())
            return Response(TaskHistorySerializer(entry).data)
        entries = task.history_entries.all()
        return Response(TaskHistorySerializer(entries, many=True).data)


