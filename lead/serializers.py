from rest_framework import serializers
from .models import Lead, LeadHistory, RegistrationGroup, LeadTag, SponsorshipType  


class LeadListSerializer(serializers.ModelSerializer):
    """
    Serializer for Lead list view (minimal fields for performance)
    """
    full_name = serializers.ReadOnlyField()
    status_display = serializers.ReadOnlyField()
    title_display = serializers.CharField(source='get_title_display', read_only=True)
    lead_type_display = serializers.CharField(source='get_lead_type_display', read_only=True)
    intensity_display = serializers.CharField(source='get_intensity_display', read_only=True)
    tag_list = serializers.ReadOnlyField()
    custom_email_list = serializers.ReadOnlyField()
    
    class Meta:
        model = Lead
        fields = [
            'id', 'title', 'title_display', 'first_name', 'last_name', 'full_name',
            'company_name', 'contact_number', 'email_address', 'custom_email_addresses',
            'custom_email_list', 'address', 'event', 'lead_type', 'lead_type_display',
            'booth_size', 'sponsorship_type', 'registration_groups', 'status',
            'status_display', 'intensity', 'intensity_display', 'opportunity_price',
            'tags', 'tag_list', 'how_did_you_hear', 'reason_for_enquiry',
            'assigned_sales_staff', 'date_received', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'date_received', 'created_at', 'updated_at']


class LeadDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for Lead detail view (all fields)
    """
    # full_name = serializers.ReadOnlyField()
    # display_name = serializers.ReadOnlyField()
    # status_display = serializers.ReadOnlyField()
    # title_display = serializers.CharField(source='get_title_display', read_only=True)
    # lead_type_display = serializers.CharField(source='get_lead_type_display', read_only=True)
    # intensity_display = serializers.CharField(source='get_intensity_display', read_only=True)
    tag_list = serializers.ReadOnlyField()
    custom_email_list = serializers.ReadOnlyField()
    
    class Meta:
        model = Lead
        fields = [
            'id', 'title', 'first_name', 'last_name','company_name', 'contact_number', 'email_address', 'custom_email_addresses', 'custom_email_list', 'address', 'event',
            'lead_type', 'booth_size', 'sponsorship_type','registration_groups', 'status', 'intensity', 'opportunity_price', 'tags', 'tag_list', 'how_did_you_hear', 'reason_for_enquiry', 'assigned_sales_staff', 'date_received', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'date_received', 'created_at', 'updated_at']


class LeadCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for Lead create and update operations
    """
    sponsorship_type = serializers.PrimaryKeyRelatedField(
        queryset=SponsorshipType.objects.all(), many=True, required=False
    )
    registration_groups = serializers.PrimaryKeyRelatedField(
        queryset=RegistrationGroup.objects.all(), many=True, required=False
    )
    tags = serializers.PrimaryKeyRelatedField(
        queryset=LeadTag.objects.all(), many=True, required=False
    )
    
    class Meta:
        model = Lead
        fields = [
            'title', 'first_name', 'last_name', 'company_name', 'contact_number',
            'email_address', 'custom_email_addresses', 'address', 'event',
            'lead_type', 'booth_size', 'sponsorship_type', 'registration_groups',
            'status', 'intensity', 'opportunity_price', 'tags', 'how_did_you_hear',
            'reason_for_enquiry', 'assigned_sales_staff'
        ]
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'company_name': {'required': True},
            'contact_number': {'required': True},
            'email_address': {'required': True},
        }
    
    def validate_email_address(self, value):
        """
        Validate email uniqueness
        """
        if self.instance is None:  # Creating new lead
            if Lead.objects.filter(email_address=value).exists():
                raise serializers.ValidationError("A lead with this email already exists.")
        else:  # Updating existing lead
            if Lead.objects.filter(email_address=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError("A lead with this email already exists.")
        return value
    
    def validate_custom_email_addresses(self, value):
        """
        Validate custom email addresses format
        """
        if value:
            emails = [email.strip() for email in value.split(',') if email.strip()]
            for email in emails:
                # Basic email validation
                if '@' not in email or '.' not in email:
                    raise serializers.ValidationError(f"Invalid email format: {email}")
        return value


class LeadStatsSerializer(serializers.Serializer):
    """
    Serializer for lead statistics
    """
    total_leads = serializers.IntegerField()
    new_leads = serializers.IntegerField()
    info_pack_leads = serializers.IntegerField()
    attempted_contact_leads = serializers.IntegerField()
    contacted_leads = serializers.IntegerField()
    contract_invoice_sent_leads = serializers.IntegerField()
    contract_signed_paid_leads = serializers.IntegerField()
    withdrawn_leads = serializers.IntegerField()
    lost_leads = serializers.IntegerField()
    converted_leads = serializers.IntegerField()
    future_leads = serializers.IntegerField()
    total_opportunity_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    exhibitor_count = serializers.IntegerField()
    sponsor_count = serializers.IntegerField()
    visitor_count = serializers.IntegerField()


class LeadBulkImportSerializer(serializers.Serializer):
    """
    Serializer for bulk lead import
    """
    leads_data = serializers.ListField(
        child=LeadCreateUpdateSerializer(),
        help_text="List of lead data to import"
    )
    
    def validate_leads_data(self, value):
        """
        Validate bulk lead data
        """
        if len(value) > 1000:  # Limit bulk import to 1000 leads
            raise serializers.ValidationError("Cannot import more than 1000 leads at once.")
        
        # Check for duplicate emails in the batch
        emails = []
        for lead_data in value:
            email = lead_data.get('email_address')
            if email in emails:
                raise serializers.ValidationError(f"Duplicate email in batch: {email}")
            emails.append(email)
        
        return value


class LeadHistorySerializer(serializers.ModelSerializer):
    lead_display = serializers.CharField(source='lead.display_name', read_only=True)

    class Meta:
        model = LeadHistory
        fields = [
            'id', 'lead', 'lead_display', 'action', 'changed_by', 'changes', 'timestamp'
        ]
        read_only_fields = ['id', 'timestamp']

class RegistrationGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistrationGroup
        fields = ['id', 'name', 'created_at', 'updated_at']

class LeadTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadTag
        fields = ['id', 'name', 'created_at', 'updated_at']

class SponsorshipTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SponsorshipType
        fields = ['id', 'name', 'created_at', 'updated_at']