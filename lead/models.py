#models file
from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone


class Lead(models.Model):
    """
    Lead model for CRM system with comprehensive lead management
    """
    
    # Lead Status Choices
    STATUS_CHOICES = [
        ('new', 'New'),
        ('info_pack', 'Info Pack'),
        ('attempted_contact', 'Attempted Contact'),
        ('contacted', 'Contacted'),
        ('contract_invoice_sent', 'Contract & Invoice Sent'),
        ('contract_signed_paid', 'Contract Signed & Paid'),
        ('withdrawn', 'Withdrawn'),
        ('lost', 'Lost'),
        ('converted', 'Converted'),
        ('future', 'Future'),
    ]
    
    # Title Choices
    TITLE_CHOICES = [
        ('mr', 'Mr'),
        ('mrs', 'Mrs'),
        ('miss', 'Miss'),
        ('ms', 'Ms'),
        ('other', 'Other'),
    ]
    
    # Type Choices
    TYPE_CHOICES = [
        ('exhibitor', 'Exhibitor'),
        ('sponsor', 'Sponsor'),
        ('visitor', 'Visitor'),
    ]
    
    # Intensity Choices
    INTENSITY_CHOICES = [
        ('cold', 'Cold Lead'),
        ('warm', 'Warm Lead'),
        ('hot', 'Hot Lead'),
        ('sql', 'Sales Qualified Lead (SQL)'),
    ]
    
    # Personal Information
    title = models.CharField(
        max_length=10,
        choices=TITLE_CHOICES,
        default='mr',
        help_text="Title: Mr, Mrs, Miss, Ms, Other"
    )
    first_name = models.CharField(
        max_length=100,
        help_text="Lead's first name"
    )
    last_name = models.CharField(
        max_length=100,
        help_text="Lead's last name"
    )
    company_name = models.CharField(
        max_length=200,
        help_text="Company name"
    )
    
    # Contact Information
    contact_number = models.CharField(
        max_length=20,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
        )],
        help_text="Contact phone number"
    )
    email_address = models.EmailField(
        help_text="Primary email address"
    )
    custom_email_addresses = models.TextField(
        blank=True,
        null=True,
        help_text="Additional email addresses (comma-separated)"
    )
    address = models.TextField(
        blank=True,
        null=True,
        help_text="Full address"
    )
    
    # Lead Details
    event = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Associated event"
    )
    lead_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='exhibitor',
        help_text="Type of lead: Exhibitor, Sponsor, Visitor"
    )
    booth_size = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Booth size preference"
    )
    sponsorship_type = models.ManyToManyField(
        'SponsorshipType',
        blank=True,
        related_name='leads',
        help_text="Selected sponsorship type"
    )
    registration_groups = models.ManyToManyField(
        'RegistrationGroup',
        blank=True,
        related_name='leads',
        help_text="Selected registration group"
    )
    
    # Lead Management
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='new',
        help_text="Current lead status"
    )
    intensity = models.CharField(
        max_length=20,
        choices=INTENSITY_CHOICES,
        default='cold',
        help_text="Lead intensity level"
    )
    opportunity_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Opportunity price/value"
    )
    tags = models.ManyToManyField(
        'LeadTag',
        blank=True,
        related_name='leads',
        help_text="Selected lead tag"
    )
    
    # Lead Source
    how_did_you_hear = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="How did they hear about us"
    )
    reason_for_enquiry = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for enquiry"
    )
    
    # Assignment
    assigned_sales_staff = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Assigned sales staff member"
    )
    
    # Timestamps
    date_received = models.DateTimeField(
        auto_now_add=True,
        help_text="Date when lead was received"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'leads'
        ordering = ['-date_received']
        verbose_name = 'Lead'
        verbose_name_plural = 'Leads'
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.company_name}"
    
    @property
    def full_name(self):
        """Return the full name of the lead"""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def display_name(self):
        """Return the display name with title"""
        return f"{self.get_title_display()} {self.full_name}"
    
    @property
    def status_display(self):
        """Return the current status of the lead"""
        return self.get_status_display()
    
    @property
    def tag_list(self):
        """Return tags as a list of names"""
        return [t.name for t in self.tags.all()]

class LeadHistory(models.Model):
    """
    Audit history for Lead changes
    """
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('read', 'Read'),
    ]

    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name='history_entries',
        help_text='Lead this history entry pertains to'
    )
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    changed_by = models.CharField(max_length=200, blank=True, null=True, help_text='Actor performing change if known')
    changes = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'lead_history'
        ordering = ['-timestamp']
        verbose_name = 'Lead History'
        verbose_name_plural = 'Lead History'

    def __str__(self):
        return f"LeadHistory(lead_id={self.lead_id}, action={self.action}, at={self.timestamp})"
    
    @property
    def custom_email_list(self):
        """Return custom emails as a list"""
        if self.custom_email_addresses:
            return [email.strip() for email in self.custom_email_addresses.split(',') if email.strip()]
        return []


class RegistrationGroup(models.Model):
    """
    Registration groups for leads
    """
    name = models.CharField(
        max_length=200,
        unique=True,
        help_text="Name of the registration group"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'registration_groups'
        ordering = ['name']
        verbose_name = 'Registration Group'
        verbose_name_plural = 'Registration Groups'

    def __str__(self):
        return self.name

class LeadTag(models.Model):
    """
    Tags for leads
    """
    name = models.CharField(
        max_length=200,
        unique=True,
        help_text="Name of the tag"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'lead_tags'
        ordering = ['name']
        verbose_name = 'Lead Tag'
        verbose_name_plural = 'Lead Tags'

    def __str__(self):
        return self.name

class SponsorshipType(models.Model):
    """
    Sponsorship types for leads
    """
    name = models.CharField(
        max_length=200,
        unique=True,
        help_text="Name of the sponsorship type"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'sponsorship_types'
        ordering = ['name']
        verbose_name = 'Sponsorship Type'
        verbose_name_plural = 'Sponsorship Types'

    def __str__(self):
        return self.name