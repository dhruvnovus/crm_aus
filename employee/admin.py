from django.contrib import admin
from .models import Employee, EmergencyContact, EmployeeHistory


class EmergencyContactInline(admin.TabularInline):
    """
    Inline admin for emergency contacts
    """
    model = EmergencyContact
    extra = 1
    fields = ['name', 'relationship', 'phone', 'email', 'address']


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    """
    Admin configuration for Employee model
    """
    list_display = [
        'id', 'full_name', 'email', 'account_type', 'staff_type', 
        'is_active', 'is_resigned', 'position', 'created_at'
    ]
    list_filter = [
        'account_type', 'staff_type', 'is_active', 'is_resigned', 
        'gender', 'created_at', 'updated_at'
    ]
    search_fields = [
        'first_name', 'last_name', 'email', 'position', 'mobile_no', 'address'
    ]
    list_editable = ['is_active', 'is_resigned']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Account Information', {
            'fields': ('account_type', 'staff_type', 'is_active', 'is_resigned')
        }),
        ('Personal Information', {
            'fields': ('title', 'first_name', 'last_name', 'email', 'password', 'position', 'gender')
        }),
        ('Contact & Location', {
            'fields': ('date_of_birth', 'mobile_no', 'landline_no', 'language_spoken', 
                      'unit_number', 'address', 'post_code'),
            'classes': ('collapse',)
        }),
        ('Profile & Notes', {
            'fields': ('profile_image', 'admin_notes'),
            'classes': ('collapse',)
        }),
        ('Contracted Hours', {
            'fields': ('hours_per_week',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [EmergencyContactInline]
    
    def get_queryset(self, request):
        """
        Optimize queryset for admin list view
        """
        return super().get_queryset(request).select_related()


@admin.register(EmergencyContact)
class EmergencyContactAdmin(admin.ModelAdmin):
    """
    Admin configuration for EmergencyContact model
    """
    list_display = ['name', 'relationship', 'phone', 'employee', 'created_at']
    list_filter = ['relationship', 'created_at']
    search_fields = ['name', 'phone', 'email', 'employee__first_name', 'employee__last_name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Contact Information', {
            'fields': ('employee', 'name', 'relationship', 'phone', 'email')
        }),
        ('Address', {
            'fields': ('address',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(EmployeeHistory)
class EmployeeHistoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'employee', 'action', 'changed_by', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['employee__first_name', 'employee__last_name', 'employee__email']
    readonly_fields = ['employee', 'action', 'changed_by', 'changes', 'timestamp']
