import json

from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import Customer
from employee.serializers import Base64ImageField
PHONE_NUMBER_VALIDATOR = RegexValidator(
	regex=r'^\+?1?\d{9,15}$',
	message="Phone number must be in format '+999999999'. Up to 15 digits allowed."
)


class CustomerListSerializer(serializers.ModelSerializer):
	"""
	Serializer for Customer list view (minimal fields for performance)
	"""
	full_name = serializers.SerializerMethodField()
	type_display = serializers.CharField(source='get_type_display', read_only=True)
	company_logo = serializers.CharField(required=False, allow_blank=True, allow_null=True)
	contact_number = serializers.CharField(source='mobile_phone', read_only=True)
	email_address = serializers.EmailField(source='email', read_only=True)
	secondary_mobile_numbers = serializers.ListField(
		child=serializers.CharField(), 
		required=False,
		allow_empty=True,
		allow_null=True,
		read_only=True
	)
	secondary_mobile_phone_code = serializers.ListField(
		child=serializers.CharField(),
		required=False,
		allow_empty=True,
		allow_null=True,
		read_only=True
	)
	secondary_mobile_type = serializers.ListField(
		child=serializers.CharField(),
		required=False,
		allow_empty=True,
		allow_null=True,
		read_only=True
	)
	class Meta:
		model = Customer
		fields = [
			'id', 'first_name', 'last_name', 'full_name', 'company_name', 'company_logo',
			'contact_number', 'mobile_phone_code', 'email_address', 'secondary_mobile_numbers',
			'secondary_mobile_phone_code', 'secondary_mobile_type',
			'address', 'abn_no', 'position',
			'type', 'type_display', 'event', 'created_at', 'updated_at', 'is_deleted'
		]
		read_only_fields = ['id', 'created_at', 'updated_at', 'is_deleted']

	def get_full_name(self, obj):
		"""Return full name combining first_name and last_name"""
		return f"{obj.first_name} {obj.last_name}".strip()


class CustomerDetailSerializer(serializers.ModelSerializer):
	"""
	Serializer for Customer detail view (all fields)
	"""
	full_name = serializers.SerializerMethodField()
	type_display = serializers.CharField(source='get_type_display', read_only=True)
	company_logo = serializers.CharField(required=False, allow_blank=True, allow_null=True)
	contact_number = serializers.CharField(source='mobile_phone', read_only=True)
	email_address = serializers.EmailField(source='email', read_only=True)
	secondary_mobile_numbers = serializers.ListField(
		child=serializers.CharField(), 
		required=False,
		allow_empty=True,
		allow_null=True,
		read_only=True
	)
	secondary_mobile_phone_code = serializers.ListField(
		child=serializers.CharField(),
		required=False,
		allow_empty=True,
		allow_null=True,
		read_only=True
	)
	secondary_mobile_type = serializers.ListField(
		child=serializers.CharField(),
		required=False,
		allow_empty=True,
		allow_null=True,
		read_only=True
	)

	class Meta:
		model = Customer
		fields = [
			'id', 'first_name', 'last_name', 'full_name', 'company_name', 'company_logo',
			'contact_number', 'mobile_phone_code', 'email_address', 'secondary_mobile_numbers',
			'secondary_mobile_phone_code', 'secondary_mobile_type',
			'address', 'abn_no', 'position',
			'password', 'type', 'type_display', 'event', 'created_at', 'updated_at', 'is_deleted'
		]
		read_only_fields = ['id', 'created_at', 'updated_at', 'is_deleted']
		extra_kwargs = {
			'password': {'write_only': True}
		}

	def get_full_name(self, obj):
		"""Return full name combining first_name and last_name"""
		return f"{obj.first_name} {obj.last_name}".strip()


class CustomerSerializer(serializers.ModelSerializer):
	# Store raw Base64 string (or empty) directly in DB
	company_logo = serializers.CharField(required=False, allow_blank=True, allow_null=True)
	full_name = serializers.SerializerMethodField()
	secondary_mobile_numbers = serializers.ListField(
		child=serializers.CharField(), 
		required=False,
		allow_empty=True,
		allow_null=True
	)
	secondary_mobile_phone_code = serializers.ListField(
		child=serializers.CharField(),
		required=False,
		allow_empty=True,
		allow_null=True
	)
	secondary_mobile_type = serializers.ListField(
		child=serializers.CharField(),
		required=False,
		allow_empty=True,
		allow_null=True
	)

	class Meta:
		model = Customer
		fields = [
			'id', 'first_name', 'last_name', 'full_name', 'company_name', 'company_logo',
			'mobile_phone', 'mobile_phone_code', 'secondary_mobile_numbers', 'secondary_mobile_phone_code', 'secondary_mobile_type', 'email', 'address', 'abn_no', 'position',
			'type', 'event', 'is_deleted', 'created_at', 'updated_at'
		]
		read_only_fields = ['id', 'created_at', 'updated_at', 'is_deleted']

	def get_full_name(self, obj):
		"""Return full name combining first_name and last_name"""
		return f"{obj.first_name} {obj.last_name}".strip()


class CustomerCreateSerializer(serializers.ModelSerializer):
	# Accept raw Base64 string (or empty) without decoding
	company_logo = serializers.CharField(required=False, allow_blank=True, allow_null=True)
	full_name = serializers.SerializerMethodField()
	secondary_mobile_numbers = serializers.ListField(
		child=serializers.CharField(),
		required=False,
		allow_empty=True,
		allow_null=True
	)
	secondary_mobile_phone_code = serializers.ListField(
		child=serializers.CharField(),
		required=False,
		allow_empty=True,
		allow_null=True
	)
	secondary_mobile_type = serializers.ListField(
		child=serializers.CharField(),
		required=False,
		allow_empty=True,
		allow_null=True
	)

	class Meta:
		model = Customer
		fields = [
			'first_name', 'last_name', 'full_name', 'company_name', 'company_logo',
			'mobile_phone', 'mobile_phone_code', 'secondary_mobile_numbers', 'secondary_mobile_phone_code',
			'secondary_mobile_type', 'email', 'address', 'abn_no', 'position',
			'password', 'type', 'event', 'is_deleted'
		]
		read_only_fields = ['is_deleted', 'full_name']
		extra_kwargs = {
			'password': {'write_only': True, 'required': True},
			'email': {'required': True},
			'first_name': {'required': True},
			'last_name': {'required': True},
			'company_name': {'required': True},
		}

	def get_full_name(self, obj):
		"""Return full name combining first_name and last_name"""
		return f"{obj.first_name} {obj.last_name}".strip()

	def _normalize_list_input(self, value, field_name):
		if value in (None, '', []):
			return []
		if isinstance(value, list):
			return value
		if isinstance(value, tuple):
			return list(value)
		if isinstance(value, str):
			clean_value = value.strip()
			if not clean_value:
				return []
			try:
				decoded = json.loads(clean_value)
				if isinstance(decoded, list):
					return decoded
			except Exception:
				pass
			return [clean_value]
		raise serializers.ValidationError({field_name: "Provide values as an array or JSON list."})

	def validate_secondary_mobile_numbers(self, value):
		numbers = self._normalize_list_input(value, 'secondary_mobile_numbers')
		cleaned = []
		for raw in numbers:
			number = str(raw).strip()
			if not number:
				continue
			try:
				PHONE_NUMBER_VALIDATOR(number)
			except DjangoValidationError:
				raise serializers.ValidationError(
					"Each secondary number must be in the format '+999999999' (9-15 digits)."
				)
			cleaned.append(number)
		return cleaned

	def validate_secondary_mobile_phone_code(self, value):
		codes = self._normalize_list_input(value, 'secondary_mobile_phone_code')
		return [str(item).strip() for item in codes if str(item).strip()]

	def validate(self, attrs):
		# normalize and trim email and password
		email = attrs.get('email')
		if email:
			attrs['email'] = email.strip().lower()

		if 'password' in attrs:
			attrs['password'] = (attrs.get('password') or '').strip()

		numbers = attrs.get('secondary_mobile_numbers')
		codes = attrs.get('secondary_mobile_phone_code')

		if numbers is not None and 'secondary_mobile_phone_code' not in attrs:
			attrs['secondary_mobile_phone_code'] = []
			codes = []

		if codes is not None and numbers is None:
			existing_numbers = []
			if self.instance:
				existing_numbers = getattr(self.instance, 'secondary_mobile_numbers', []) or []
			if not existing_numbers and codes:
				raise serializers.ValidationError({
					'secondary_mobile_phone_code': 'Provide at least one secondary number before adding country codes.'
				})

		numbers_final = numbers
		if numbers_final is None and self.instance:
			numbers_final = getattr(self.instance, 'secondary_mobile_numbers', []) or []
		codes_final = attrs.get('secondary_mobile_phone_code')
		if codes_final is None and self.instance:
			codes_final = getattr(self.instance, 'secondary_mobile_phone_code', []) or []

		if numbers_final and codes_final and len(codes_final) not in (0, len(numbers_final)):
			raise serializers.ValidationError({
				'secondary_mobile_phone_code': 'Provide the same number of country codes as secondary numbers or leave the codes empty.'
			})

		return attrs

	def validate_password(self, value):
		if value:
			return make_password(value)
		return value

	def create(self, validated_data):
		return Customer.objects.create(**validated_data)


