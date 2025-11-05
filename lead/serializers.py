from rest_framework import serializers
from .models import Lead, LeadHistory, RegistrationGroup, LeadTag, SponsorshipType
from employee.models import Employee
from employee.serializers import EmployeeListSerializer, EmployeeDetailSerializer  
from customers.models import Customer
from django.db import transaction
from django.contrib.auth.hashers import make_password
import uuid


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
    assigned_sales_staff = EmployeeListSerializer(read_only=True)
    
    class Meta:
        model = Lead
        fields = [
            'id', 'title', 'title_display', 'first_name', 'last_name', 'full_name',
            'company_name', 'contact_number', 'email_address', 'custom_email_addresses',
            'custom_email_list', 'address', 'event', 'lead_type', 'lead_type_display',
            'booth_size', 'sponsorship_type', 'registration_groups', 'status',
            'status_display', 'intensity', 'intensity_display', 'opportunity_price',
            'tags', 'tag_list', 'how_did_you_hear', 'reason_for_enquiry',
            'assigned_sales_staff', 'lead_name', 'lead_pipeline', 'lead_stage',
            'date_received', 'created_at', 'updated_at', 'is_deleted'
        ]
        read_only_fields = ['id', 'date_received', 'created_at', 'updated_at', 'is_deleted']



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
    assigned_sales_staff = EmployeeDetailSerializer(read_only=True)
    
    class Meta:
        model = Lead
        fields = [
            'id', 'title', 'first_name', 'last_name','company_name', 'contact_number', 'email_address', 'custom_email_addresses', 'custom_email_list', 'address', 'event',
            'lead_type', 'booth_size', 'sponsorship_type','registration_groups', 'status', 'intensity', 'opportunity_price', 'tags', 'tag_list', 'how_did_you_hear', 'reason_for_enquiry', 'assigned_sales_staff', 'lead_name', 'lead_pipeline', 'lead_stage', 'date_received', 'created_at', 'updated_at', 'is_deleted'
        ]
        read_only_fields = ['id', 'date_received', 'created_at', 'updated_at', 'is_deleted']


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
    assigned_sales_staff = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.filter(is_deleted=False), required=False, allow_null=True
    )
    employee_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    customer_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Lead
        fields = [
            'title', 'first_name', 'last_name', 'company_name', 'contact_number',
            'email_address', 'custom_email_addresses', 'address', 'event',
            'lead_type', 'booth_size', 'sponsorship_type', 'registration_groups',
            'status', 'intensity', 'opportunity_price', 'tags', 'how_did_you_hear',
            'reason_for_enquiry', 'assigned_sales_staff', 'employee_id', 'customer_id', 'lead_name', 'lead_pipeline', 'lead_stage'
        ]
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'company_name': {'required': True},
            'contact_number': {'required': True},
            'email_address': {'required': True},
            'assigned_sales_staff': {'required': False, 'allow_null': True},
        }
    
    def validate(self, attrs):
        """
        Handle employee_id mapping to assigned_sales_staff
        employee_id takes precedence over assigned_sales_staff if both are provided
        """
        employee_id = attrs.pop('employee_id', None)
        if employee_id is not None:
            # If employee_id is provided, use it to set assigned_sales_staff (takes precedence)
            try:
                employee = Employee.objects.get(id=employee_id, is_deleted=False)
                attrs['assigned_sales_staff'] = employee
            except Employee.DoesNotExist:
                raise serializers.ValidationError({"employee_id": f"Employee with id {employee_id} not found."})
        # If employee_id is not provided, keep assigned_sales_staff as is (or None if not provided)
        return attrs
    
    def validate_email_address(self, value):
        """
        Normalize email address; duplicates are allowed by requirement.
        """
        return (value or '').strip().lower()
    
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
    
    def create(self, validated_data):
        sponsorship_types = validated_data.pop('sponsorship_type', [])
        registration_groups = validated_data.pop('registration_groups', [])
        tags = validated_data.pop('tags', [])
        # Remove write-only passthrough field so it is not sent to Lead.create
        customer_id = validated_data.pop('customer_id', None)

        with transaction.atomic():
            # Attach or create customer
            if customer_id:
                try:
                    customer = Customer.objects.get(id=customer_id, is_deleted=False)
                except Customer.DoesNotExist:
                    raise serializers.ValidationError({"customer_id": f"Customer with id {customer_id} not found."})
            else:
                # Try to find by email; otherwise create a minimal customer from lead data
                email = (validated_data.get('email_address') or '').strip().lower()
                customer = None
                if email:
                    customer = Customer.objects.filter(email=email, is_deleted=False).first()
                if customer is None:
                    customer = Customer.objects.create(
                        first_name=validated_data.get('first_name', ''),
                        last_name=validated_data.get('last_name', ''),
                        company_name=validated_data.get('company_name', ''),
                        mobile_phone=validated_data.get('contact_number', ''),
                        email=email,
                        address=validated_data.get('address'),
                        type=(validated_data.get('lead_type') if validated_data.get('lead_type') in ['exhibitor', 'sponsor'] else 'exhibitor'),
                        event=validated_data.get('event'),
                        password=make_password(uuid.uuid4().hex),
                    )

            # create lead with linked customer
            lead = Lead.objects.create(customer=customer, **validated_data)

            # Fallback: if for any reason FK didn't persist, set and save
            if not lead.customer_id and customer:
                lead.customer = customer
                lead.save(update_fields=['customer'])

            if sponsorship_types:
                lead.sponsorship_type.set(sponsorship_types)
            if registration_groups:
                lead.registration_groups.set(registration_groups)
            if tags:
                lead.tags.set(tags)

        return lead


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

        # Duplicates within the batch are allowed as per requirement
        return value

    # No custom create here; we validate only. Lead creation is handled by LeadCreateUpdateSerializer


class LeadHistorySerializer(serializers.ModelSerializer):
    lead_display = serializers.CharField(source='lead.display_name', read_only=True)

    class Meta:
        model = LeadHistory
        fields = [
            'id', 'lead', 'lead_display', 'action', 'changed_by', 'changes', 'timestamp', 'is_deleted'
        ]
        read_only_fields = ['id', 'timestamp', 'is_deleted']

class RegistrationGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistrationGroup
        fields = ['id', 'name', 'created_at', 'updated_at', 'is_deleted']
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_deleted']

class LeadTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadTag
        fields = ['id', 'name', 'created_at', 'updated_at', 'is_deleted']
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_deleted']

class SponsorshipTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SponsorshipType
        fields = ['id', 'name', 'created_at', 'updated_at', 'is_deleted']
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_deleted']