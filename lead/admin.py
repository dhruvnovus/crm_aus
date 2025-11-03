from django.contrib import admin
from .models import Lead, LeadHistory , RegistrationGroup , LeadTag, SponsorshipType


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'full_name', 'company_name', 'email_address', 'contact_number',
        'lead_type', 'status', 'intensity', 'opportunity_price', 'assigned_sales_staff',
        'event', 'date_received', 'created_at'
    ]
    list_filter = [
        'status', 'lead_type', 'intensity', 'assigned_sales_staff', 'event',
        'title', 'date_received', 'created_at', 'updated_at'
    ]
    search_fields = [
        'first_name', 'last_name', 'company_name', 'email_address',
        'contact_number', 'tags', 'event', 'assigned_sales_staff'
    ]
    list_editable = ['status', 'intensity', 'assigned_sales_staff']
    readonly_fields = ['date_received', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('title', 'first_name', 'last_name', 'company_name')
        }),
        ('Contact Information', {
            'fields': ('contact_number', 'email_address', 'custom_email_addresses', 'address')
        }),
        ('Lead Details', {
            'fields': ('event', 'lead_type', 'booth_size', 'sponsorship_type', 'registration_groups')
        }),
        ('Lead Management', {
            'fields': ('status', 'intensity', 'opportunity_price', 'tags', 'assigned_sales_staff')
        }),
        ('Lead Source', {
            'fields': ('how_did_you_hear', 'reason_for_enquiry'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('date_received', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request)
    
    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = 'Full Name'
    full_name.admin_order_field = 'first_name'


@admin.register(LeadHistory)
class LeadHistoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'lead', 'action', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['lead__first_name', 'lead__last_name', 'lead__company_name']
    readonly_fields = ['lead', 'action', 'changed_by', 'changes', 'timestamp']

@admin.register(RegistrationGroup)
class RegistrationGroupAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Registration Group', {
            'fields': ('name',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(LeadTag)
class LeadTagAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Lead Tag', {
            'fields': ('name',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'), 
            'classes': ('collapse',)
        }),
    )

@admin.register(SponsorshipType)
class SponsorshipTypeAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Sponsorship Type', {
            'fields': ('name',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )