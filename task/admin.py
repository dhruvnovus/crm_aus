from django.contrib import admin
from .models import Task, Subtask, TaskAttachment, TaskReminder, TaskHistory


class SubtaskInline(admin.TabularInline):
    model = Subtask
    fk_name = 'parent_task'
    extra = 0


class TaskAttachmentInline(admin.TabularInline):
    model = TaskAttachment
    extra = 0


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'assigned_to', 'priority', 'status', 'due_date', 'due_time', 'is_deleted')
    list_filter = ('priority', 'status', 'is_deleted')
    search_fields = ('title', 'description')
    inlines = [SubtaskInline, TaskAttachmentInline]


admin.site.register(Subtask)
admin.site.register(TaskAttachment)
admin.site.register(TaskReminder)
admin.site.register(TaskHistory)


