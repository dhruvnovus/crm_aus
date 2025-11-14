from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from django.core.files.base import ContentFile
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
import base64
import uuid
from role.models import Role
from .models import Employee, EmergencyContact, EmployeeHistory, PasswordResetToken


class Base64ImageField(serializers.Field):
    """
    A Django REST framework field for handling image-uploads through raw post data.
    It uses base64 for encoding and decoding the contents of the file.
    """
    
    def to_internal_value(self, data):
        # Handle empty strings or None - return None to store as empty
        if not data or (isinstance(data, str) and not data.strip()):
            return None
        
        # Check if this is a base64 string
        if isinstance(data, str):
            # Extract base64 content if it's in "data:image/jpeg;base64,..." format
            if 'data:' in data and ';base64,' in data:
                # Break out the header from the base64 content
                header, base64_content = data.split(';base64,')
                # Return the full base64 string (with data: prefix) for storage
                return data
            else:
                # If it's already a plain base64 string, validate it
                try:
                    # Try to decode to validate it's valid base64
                    base64.b64decode(data)
                    # Return the base64 string as-is for storage
                    return data
                except (TypeError, ValueError):
                    raise serializers.ValidationError("Invalid base64 string")
        
        raise serializers.ValidationError("Invalid image format. Expected base64 string.")
    
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
            'created_at', 'updated_at', 'is_deleted'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_deleted']


class RoleBasicSerializer(serializers.ModelSerializer):
    """
    Basic role serializer for including in employee response
    """
    name_display = serializers.CharField(source='get_name_display', read_only=True)
    
    class Meta:
        model = Role
        fields = ['id', 'name', 'name_display', 'display_name', 'description', 'is_active']
        read_only_fields = ['id', 'name', 'name_display', 'display_name', 'description', 'is_active']


class EmployeeListSerializer(serializers.ModelSerializer):
    """
    Serializer for Employee list view (minimal fields for performance)
    """
    full_name = serializers.ReadOnlyField()
    status_display = serializers.ReadOnlyField()
    # account_type_display = serializers.CharField(source='get_account_type_display', read_only=True)
    staff_type_display = serializers.CharField(source='get_staff_type_display', read_only=True)
    profile_image = serializers.ImageField(required=False, allow_null=True)
    role = RoleBasicSerializer(read_only=True)
    
    class Meta:
        model = Employee
        fields = [
            'id', 'account_type', 'staff_type', 'staff_type_display', 
            'is_active', 'is_resigned', 'title', 'first_name', 'last_name', 'full_name',
            'email', 'position', 'gender', 'mobile_no', 'address', 'post_code',
            'profile_image', 'hours_per_week', 'status_display', 'role',
            'created_at', 'updated_at', 'is_deleted'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_deleted']


class EmployeeDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for Employee detail view (all fields)
    """
    full_name = serializers.ReadOnlyField()
    display_name = serializers.ReadOnlyField()
    status_display = serializers.ReadOnlyField()
    # account_type_display = serializers.CharField(source='get_account_type_display', read_only=True)
    staff_type_display = serializers.CharField(source='get_staff_type_display', read_only=True)
    title_display = serializers.CharField(source='get_title_display', read_only=True)
    gender_display = serializers.CharField(source='get_gender_display', read_only=True)
    emergency_contacts = EmergencyContactSerializer(many=True, read_only=True)
    profile_image = serializers.ImageField(required=False, allow_null=True)
    role = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            'id', 'account_type', 'staff_type', 'staff_type_display',
            'is_active', 'is_resigned', 'title', 'title_display', 'first_name', 'last_name',
            'full_name', 'display_name', 'email', 'password', 'position', 'gender', 'gender_display',
            'date_of_birth', 'mobile_no', 'landline_no', 'language_spoken', 'unit_number',
            'address', 'post_code', 'profile_image', 'admin_notes', 'hours_per_week',
            'status_display', 'emergency_contacts', 'role', 'created_at', 'updated_at', 'is_deleted'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_deleted']
        extra_kwargs = {
            'password': {'write_only': True}
        }
    
    def get_role(self, obj):
        """Get role information if role is assigned"""
        if obj.role:
            return {
                'id': obj.role.id,
                'name': obj.role.name,
                'name_display': obj.role.get_name_display(),
                'display_name': obj.role.display_name,
                'description': obj.role.description,
                'is_active': obj.role.is_active
            }
        return None
    
    def get_permissions(self, obj):
        """Get all permissions for this employee"""
        return obj.get_permissions()


class EmployeeCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for Employee create and update operations
    """
    emergency_contacts = EmergencyContactSerializer(many=True, required=False)
    profile_image = serializers.ImageField(required=False, allow_null=True)
    role_id = serializers.IntegerField(required=False, allow_null=True)
    
    class Meta:
        model = Employee
        fields = [
            'account_type', 'staff_type', 'is_active', 'is_resigned', 'title',
            'first_name', 'last_name', 'email', 'password', 'position', 'gender',
            'date_of_birth', 'mobile_no', 'landline_no', 'language_spoken',
            'unit_number', 'address', 'post_code', 'profile_image', 'admin_notes',
            'hours_per_week', 'emergency_contacts', 'role_id', 'is_deleted'
        ]
        read_only_fields = ['is_deleted']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False, 'allow_blank': True},
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
            'gender': {'required': True},
            'account_type': {'required': False},
            'staff_type': {'required': True}
        }
    
    def validate_email(self, value):
        """
        Validate email uniqueness for updates only
        For creates, let database enforce uniqueness (faster, avoids extra query)
        """
        if self.instance is not None:  # Updating existing employee
            if Employee.objects.filter(email=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError("An employee with this email already exists.")
        return value

    def validate_role_id(self, value):
        """
        Validate that the provided role exists (if supplied)
        """
        if value is None:
            return value
        if not Role.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Invalid role ID.")
        return value
    
    def validate_password(self, value):
        """
        Hash password before saving
        """
        # If password is None or not provided, don't validate (allow None for updates)
        if value is None:
            return None
        
        # If password is an empty string, return None (don't update password)
        if isinstance(value, str) and not value.strip():
            return None
        
        # If password is provided and not empty, hash it
        if value:
            return make_password(value)
        
        # Fallback: return None
        return None
    
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
        role_id = validated_data.pop('role_id', None)
        
        employee = Employee.objects.create(**validated_data)

        if role_id is not None:
            employee.role_id = role_id
            employee.save(update_fields=['role'])
        
        # Use bulk_create for better performance instead of individual creates
        if emergency_contacts_data:
            contacts = [
                EmergencyContact(employee=employee, **contact_data)
                for contact_data in emergency_contacts_data
            ]
            EmergencyContact.objects.bulk_create(contacts)
        
        return employee
    
    def update(self, instance, validated_data):
        """
        Update employee and emergency contacts
        """
        emergency_contacts_data = validated_data.pop('emergency_contacts', None)
        role_id = validated_data.pop('role_id', serializers.empty)
        
        # Remove password from validated_data - handle separately
        password = validated_data.pop('password', None)
        
        # Handle profile_image explicitly
        profile_image = validated_data.pop('profile_image', serializers.empty)
        if profile_image is not serializers.empty:
            # If profile_image is None or empty string, clear it
            if profile_image is None or (isinstance(profile_image, str) and not profile_image.strip()):
                instance.profile_image = None
            else:
                instance.profile_image = profile_image
        
        # Update employee fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if role_id is not serializers.empty:
            if role_id is None:
                instance.role = None
            else:
                instance.role_id = role_id
        
        # Only update password if a new one was provided
        if password is not None:
            instance.password = password
        
        instance.save()
        
        # Refresh from database to ensure role relationship is properly loaded
        instance.refresh_from_db()
        
        if emergency_contacts_data is not None:
            instance.emergency_contacts.all().delete()
            
            if emergency_contacts_data:
                contacts = [
                    EmergencyContact(employee=instance, **contact_data)
                    for contact_data in emergency_contacts_data
                ]
                EmergencyContact.objects.bulk_create(contacts)
        
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
            'timestamp', 'is_deleted'
        ]
        read_only_fields = ['id', 'timestamp', 'is_deleted']


# Authentication Serializers

class UserLoginSerializer(serializers.Serializer):
    """
    Serializer for user login
    """
    username = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    remember_me = serializers.BooleanField(default=False, required=False)
    forgot_password = serializers.BooleanField(default=False, required=False)


class ForgotPasswordSerializer(serializers.Serializer):
    """
    Serializer for forgot password request
    """
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        """
        Validate that email exists
        """
        if not Employee.objects.filter(email=value, is_active=True).exists():
            raise serializers.ValidationError("No active employee found with this email address.")
        return value


class ResetPasswordSerializer(serializers.Serializer):
    """
    Serializer for password reset
    """
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        """
        Validate that passwords match and token is valid
        """
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Passwords don't match.")
        
        try:
            reset_token = PasswordResetToken.objects.get(token=attrs['token'])
            if not reset_token.is_valid():
                raise serializers.ValidationError("Invalid or expired token.")
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError("Invalid token.")
        
        return attrs
    
    def validate_new_password(self, value):
        """
        Validate password strength
        """
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for changing password
    """
    current_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)
    retype_new_password = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        """
        Validate that new passwords match
        """
        if attrs['new_password'] != attrs['retype_new_password']:
            raise serializers.ValidationError("New passwords don't match.")
        return attrs
    
    def validate_new_password(self, value):
        """
        Validate password strength
        """
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value


class UserResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for user response data
    """
    user_id = serializers.IntegerField(source='id', read_only=True)
    name = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = Employee
        fields = ['user_id', 'name', 'email', 'created_at']
    
    def get_name(self, obj):
        return obj.full_name


class LoginResponseSerializer(serializers.Serializer):
    """
    Serializer for login response
    """
    success = serializers.BooleanField()
    message = serializers.CharField()
    token = serializers.CharField()
    user = serializers.DictField()


class AuthResponseSerializer(serializers.Serializer):
    """
    Serializer for authentication responses (success/error)
    """
    success = serializers.BooleanField()
    message = serializers.CharField()
    errors = serializers.DictField(required=False)


class RegistrationResponseSerializer(serializers.Serializer):
    """
    Serializer for registration response
    """
    success = serializers.BooleanField()
    message = serializers.CharField()
    data = UserResponseSerializer()
