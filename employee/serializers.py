from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from django.core.files.base import ContentFile
import base64
import uuid
from .models import Employee, EmergencyContact, EmployeeHistory


class Base64ImageField(serializers.Field):
    """
    A Django REST framework field for handling image-uploads through raw post data.
    It uses base64 for encoding and decoding the contents of the file.
    """
    
    def to_internal_value(self, data):
        # Check if this is a base64 string
        if isinstance(data, str):
            # Check if the base64 string is in the "data:" format
            if 'data:' in data and ';base64,' in data:
                # Break out the header from the base64 content
                header, data = data.split(';base64,')
            
            # Try to decode the file. Return validation error if it fails.
            try:
                decoded_file = base64.b64decode(data)
            except TypeError:
                raise serializers.ValidationError("Invalid base64 string")
            
            # Generate file name
            file_name = str(uuid.uuid4())[:12]  # 12 characters are more than enough.
            
            # Get the file name extension
            file_extension = self.get_file_extension(file_name, decoded_file)
            complete_file_name = "%s.%s" % (file_name, file_extension,)
            
            return complete_file_name, decoded_file
        
        raise serializers.ValidationError("Invalid image format")
    
    def to_representation(self, value):
        # Return the base64 string if it exists, otherwise return None
        if value:
            return value
        return None
    
    def get_file_extension(self, filename, decoded_file):
        """
        Determine the file extension from the decoded file content
        """
        import imghdr
        
        extension = imghdr.what(filename, decoded_file)
        extension = "jpg" if extension == "jpeg" else extension
        
        return extension


class EmergencyContactSerializer(serializers.ModelSerializer):
    """
    Serializer for Emergency Contact model
    """
    class Meta:
        model = EmergencyContact
        fields = [
            'id', 'name', 'relationship', 'phone', 'email', 'address',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmployeeListSerializer(serializers.ModelSerializer):
    """
    Serializer for Employee list view (minimal fields for performance)
    """
    full_name = serializers.ReadOnlyField()
    status_display = serializers.ReadOnlyField()
    account_type_display = serializers.CharField(source='get_account_type_display', read_only=True)
    staff_type_display = serializers.CharField(source='get_staff_type_display', read_only=True)
    profile_image = Base64ImageField(required=False)
    
    class Meta:
        model = Employee
        fields = [
            'id', 'account_type', 'account_type_display', 'staff_type', 'staff_type_display',
            'is_active', 'is_resigned', 'title', 'first_name', 'last_name', 'full_name',
            'email', 'position', 'gender', 'mobile_no', 'address', 'post_code',
            'profile_image', 'hours_per_week', 'status_display', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmployeeDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for Employee detail view (all fields)
    """
    full_name = serializers.ReadOnlyField()
    display_name = serializers.ReadOnlyField()
    status_display = serializers.ReadOnlyField()
    account_type_display = serializers.CharField(source='get_account_type_display', read_only=True)
    staff_type_display = serializers.CharField(source='get_staff_type_display', read_only=True)
    title_display = serializers.CharField(source='get_title_display', read_only=True)
    gender_display = serializers.CharField(source='get_gender_display', read_only=True)
    emergency_contacts = EmergencyContactSerializer(many=True, read_only=True)
    profile_image = Base64ImageField(required=False)
    
    class Meta:
        model = Employee
        fields = [
            'id', 'account_type', 'account_type_display', 'staff_type', 'staff_type_display',
            'is_active', 'is_resigned', 'title', 'title_display', 'first_name', 'last_name',
            'full_name', 'display_name', 'email', 'password', 'position', 'gender', 'gender_display',
            'date_of_birth', 'mobile_no', 'landline_no', 'language_spoken', 'unit_number',
            'address', 'post_code', 'profile_image', 'admin_notes', 'hours_per_week',
            'status_display', 'emergency_contacts', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'password': {'write_only': True}
        }


class EmployeeCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for Employee create and update operations
    """
    emergency_contacts = EmergencyContactSerializer(many=True, required=False)
    profile_image = Base64ImageField(required=False)
    
    class Meta:
        model = Employee
        fields = [
            'account_type', 'staff_type', 'is_active', 'is_resigned', 'title',
            'first_name', 'last_name', 'email', 'password', 'position', 'gender',
            'date_of_birth', 'mobile_no', 'landline_no', 'language_spoken',
            'unit_number', 'address', 'post_code', 'profile_image', 'admin_notes',
            'hours_per_week', 'emergency_contacts'
        ]
        extra_kwargs = {
            'password': {'write_only': True, 'required': True},
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
            'gender': {'required': True},
            'account_type': {'required': True},
            'staff_type': {'required': True}
        }
    
    def validate_email(self, value):
        """
        Validate email uniqueness
        """
        if self.instance is None:  # Creating new employee
            if Employee.objects.filter(email=value).exists():
                raise serializers.ValidationError("An employee with this email already exists.")
        else:  # Updating existing employee
            if Employee.objects.filter(email=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError("An employee with this email already exists.")
        return value
    
    def validate_password(self, value):
        """
        Hash password before saving
        """
        if value:
            return make_password(value)
        return value
    
    def validate_emergency_contacts(self, value):
        """
        Validate emergency contacts data
        """
        if len(value) > 5:  # Limit to 5 emergency contacts
            raise serializers.ValidationError("Maximum 5 emergency contacts allowed.")
        
        for contact in value:
            if not contact.get('name'):
                raise serializers.ValidationError("Emergency contact name is required.")
            if not contact.get('relationship'):
                raise serializers.ValidationError("Emergency contact relationship is required.")
            if not contact.get('phone'):
                raise serializers.ValidationError("Emergency contact phone is required.")
        
        return value
    
    def create(self, validated_data):
        """
        Create employee with emergency contacts
        """
        emergency_contacts_data = validated_data.pop('emergency_contacts', [])
        
        # Handle profile image Base64 data
        profile_image_data = validated_data.get('profile_image')
        if profile_image_data:
            # Store the Base64 string directly in the database
            validated_data['profile_image'] = profile_image_data
        
        employee = Employee.objects.create(**validated_data)
        
        for contact_data in emergency_contacts_data:
            EmergencyContact.objects.create(employee=employee, **contact_data)
        
        return employee
    
    def update(self, instance, validated_data):
        """
        Update employee and emergency contacts
        """
        emergency_contacts_data = validated_data.pop('emergency_contacts', None)
        
        # Handle profile image Base64 data
        profile_image_data = validated_data.get('profile_image')
        if profile_image_data:
            # Store the Base64 string directly in the database
            validated_data['profile_image'] = profile_image_data
        
        # Update employee fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update emergency contacts if provided
        if emergency_contacts_data is not None:
            # Delete existing emergency contacts
            instance.emergency_contacts.all().delete()
            
            # Create new emergency contacts
            for contact_data in emergency_contacts_data:
                EmergencyContact.objects.create(employee=instance, **contact_data)
        
        return instance


class EmployeeStatsSerializer(serializers.Serializer):
    """
    Serializer for employee statistics
    """
    total_employees = serializers.IntegerField()
    active_employees = serializers.IntegerField()
    inactive_employees = serializers.IntegerField()
    resigned_employees = serializers.IntegerField()
    super_admin_count = serializers.IntegerField()
    sales_staff_count = serializers.IntegerField()
    employee_count = serializers.IntegerField()
    contractor_count = serializers.IntegerField()


class EmployeeHistorySerializer(serializers.ModelSerializer):
    employee_display = serializers.CharField(source='employee.display_name', read_only=True)

    class Meta:
        model = EmployeeHistory
        fields = [
            'id', 'employee', 'employee_display', 'action', 'changed_by', 'changes',
            'timestamp'
        ]
        read_only_fields = ['id', 'timestamp']
