from rest_framework import serializers
from .models import Lead, LeadHistory, RegistrationGroup, LeadTag, SponsorshipType
from employee.models import Employee
from employee.serializers import EmployeeListSerializer, EmployeeDetailSerializer 
from customers.models import Customer
from customers.serializers import CustomerListSerializer, CustomerDetailSerializer
from django.db import transaction
from django.contrib.auth.hashers import make_password
import uuid


class LeadListSerializer(serializers.ModelSerializer):
    """
    Serializer for Lead list view (minimal fields for performance)
    """
    full_name = serializers.ReadOnlyField()
    status_display = serializers.ReadOnlyField()
    # title_display = serializers.CharField(source='get_title_display', read_only=True)
    lead_type_display = serializers.CharField(source='get_lead_type_display', read_only=True)
    intensity_display = serializers.CharField(source='get_intensity_display', read_only=True)
    tag_list = serializers.ReadOnlyField()
    # custom_email_list = serializers.ReadOnlyField()
    assigned_sales_staff = EmployeeListSerializer(read_only=True)
    customer = CustomerListSerializer(read_only=True)
    
    class Meta:
        model = Lead
        fields = [
            'id', 'custom_email_addresses',
            'event', 'lead_type', 'lead_type_display',
            'booth_size', 'sponsorship_type', 'registration_groups', 'status',
            'status_display', 'intensity', 'intensity_display', 'opportunity_price',
            'tags', 'tag_list', 'how_did_you_hear', 'reason_for_enquiry',
            'assigned_sales_staff', 'customer', 'lead_name', 'lead_pipeline', 'lead_stage',
            'full_name', 'date_received', 'created_at', 'updated_at', 'is_deleted'
        ]
        read_only_fields = ['id', 'date_received', 'created_at', 'updated_at', 'is_deleted']



class LeadDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for Lead detail view (all fields)
    """
    full_name = serializers.ReadOnlyField()
    # display_name = serializers.ReadOnlyField()
    # status_display = serializers.ReadOnlyField()
    # title_display = serializers.CharField(source='get_title_display', read_only=True)
    # lead_type_display = serializers.CharField(source='get_lead_type_display', read_only=True)
    # intensity_display = serializers.CharField(source='get_intensity_display', read_only=True)
    tag_list = serializers.ReadOnlyField()
    # custom_email_list = serializers.ReadOnlyField()
    assigned_sales_staff = EmployeeDetailSerializer(read_only=True)
    customer = CustomerDetailSerializer(read_only=True)
    class Meta:
        model = Lead
        fields = [
            'id', 'custom_email_addresses',
            'lead_type', 'booth_size', 'sponsorship_type','registration_groups', 'status', 'intensity', 'opportunity_price', 'tags', 'tag_list', 'how_did_you_hear', 'reason_for_enquiry', 'assigned_sales_staff','customer', 'lead_name', 'lead_pipeline', 'lead_stage', 'full_name', 'date_received', 'created_at', 'updated_at', 'is_deleted'
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
                if email and email != 'noemail@example.com':
                    customer = Customer.objects.filter(email=email, is_deleted=False).first()
                if customer is None:
                    # Generate unique email if default email is used
                    if not email or email == 'noemail@example.com':
                        email = f"noemail_{uuid.uuid4().hex[:8]}@example.com"
                    try:
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
                    except Exception as e:
                        # If customer creation fails (e.g., duplicate email), try to get existing one
                        if 'email' in str(e).lower() or 'unique' in str(e).lower():
                            customer = Customer.objects.filter(email=email, is_deleted=False).first()
                            if not customer:
                                raise serializers.ValidationError({"email": f"Customer with email {email} already exists or creation failed: {str(e)}"})
                        else:
                            raise

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
    
    def update(self, instance, validated_data):
        """
        Update lead and associated customer
        """
        sponsorship_types = validated_data.pop('sponsorship_type', None)
        registration_groups = validated_data.pop('registration_groups', None)
        tags = validated_data.pop('tags', None)
        customer_id = validated_data.pop('customer_id', None)

        with transaction.atomic():
            # Update customer if lead data changed
            if instance.customer:
                customer = instance.customer
                # Update customer fields from lead data if they changed
                customer_updated = False
                
                if 'first_name' in validated_data and customer.first_name != validated_data.get('first_name'):
                    customer.first_name = validated_data.get('first_name')
                    customer_updated = True
                
                if 'last_name' in validated_data and customer.last_name != validated_data.get('last_name'):
                    customer.last_name = validated_data.get('last_name')
                    customer_updated = True
                
                if 'company_name' in validated_data and customer.company_name != validated_data.get('company_name'):
                    customer.company_name = validated_data.get('company_name')
                    customer_updated = True
                
                if 'contact_number' in validated_data and customer.mobile_phone != validated_data.get('contact_number'):
                    customer.mobile_phone = validated_data.get('contact_number')
                    customer_updated = True
                
                if 'email_address' in validated_data:
                    new_email = (validated_data.get('email_address') or '').strip().lower()
                    if customer.email != new_email and new_email:
                        customer.email = new_email
                        customer_updated = True
                
                if 'address' in validated_data and customer.address != validated_data.get('address'):
                    customer.address = validated_data.get('address')
                    customer_updated = True
                
                if 'event' in validated_data and customer.event != validated_data.get('event'):
                    customer.event = validated_data.get('event')
                    customer_updated = True
                
                if 'lead_type' in validated_data:
                    lead_type = validated_data.get('lead_type')
                    if lead_type in ['exhibitor', 'sponsor'] and customer.type != lead_type:
                        customer.type = lead_type
                        customer_updated = True
                
                if customer_updated:
                    customer.save()
            elif customer_id:
                # If customer_id is provided, link to that customer
                try:
                    customer = Customer.objects.get(id=customer_id, is_deleted=False)
                    instance.customer = customer
                except Customer.DoesNotExist:
                    raise serializers.ValidationError({"customer_id": f"Customer with id {customer_id} not found."})
            else:
                # If no customer exists, create or find one by email
                email = (validated_data.get('email_address') or '').strip().lower()
                if email and email != 'noemail@example.com':
                    customer = Customer.objects.filter(email=email, is_deleted=False).first()
                    if customer:
                        instance.customer = customer
                    else:
                        # Create new customer
                        if not email or email == 'noemail@example.com':
                            email = f"noemail_{uuid.uuid4().hex[:8]}@example.com"
                        try:
                            customer = Customer.objects.create(
                                first_name=validated_data.get('first_name', instance.first_name),
                                last_name=validated_data.get('last_name', instance.last_name),
                                company_name=validated_data.get('company_name', instance.company_name),
                                mobile_phone=validated_data.get('contact_number', instance.contact_number),
                                email=email,
                                address=validated_data.get('address', instance.address),
                                type=(validated_data.get('lead_type') if validated_data.get('lead_type') in ['exhibitor', 'sponsor'] else 'exhibitor'),
                                event=validated_data.get('event', instance.event),
                                password=make_password(uuid.uuid4().hex),
                            )
                            instance.customer = customer
                        except Exception as e:
                            if 'email' in str(e).lower() or 'unique' in str(e).lower():
                                customer = Customer.objects.filter(email=email, is_deleted=False).first()
                                if customer:
                                    instance.customer = customer
                                else:
                                    raise serializers.ValidationError({"email": f"Customer with email {email} already exists or creation failed: {str(e)}"})
                            else:
                                raise

            # Update lead fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            # Update ManyToMany relationships
            if sponsorship_types is not None:
                instance.sponsorship_type.set(sponsorship_types)
            if registration_groups is not None:
                instance.registration_groups.set(registration_groups)
            if tags is not None:
                instance.tags.set(tags)

        return instance


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