from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
import logging

from .models import Customer
from employee.serializers import Base64ImageField


class CustomerSerializer(serializers.ModelSerializer):
	# Store raw Base64 string (or empty) directly in DB
	company_logo = serializers.CharField(required=False, allow_blank=True, allow_null=True)

	class Meta:
		model = Customer
		fields = [
			'id', 'first_name', 'last_name', 'company_name', 'company_logo',
			'mobile_phone', 'email', 'address', 'abn_no', 'position',
			'type', 'event', 'is_deleted', 'created_at', 'updated_at'
		]
		read_only_fields = ['id', 'created_at', 'updated_at', 'is_deleted']


class CustomerCreateSerializer(serializers.ModelSerializer):
	# Accept raw Base64 string (or empty) without decoding
	company_logo = serializers.CharField(required=False, allow_blank=True, allow_null=True)

	class Meta:
		model = Customer
		fields = [
			'first_name', 'last_name', 'company_name', 'company_logo',
			'mobile_phone', 'email', 'address', 'abn_no', 'position',
			'password', 'type', 'event', 'is_deleted'
		]
		read_only_fields = ['is_deleted']
		extra_kwargs = {
			'password': {'write_only': True, 'required': True},
			'email': {'required': True},
			'first_name': {'required': True},
			'last_name': {'required': True},
			'company_name': {'required': True},
		}

	def validate(self, attrs):
		# normalize and trim email and password
		email = attrs.get('email')
		if email:
			attrs['email'] = email.strip().lower()
		password = (attrs.get('password') or '').strip()
		attrs['password'] = password
		return attrs

	def validate_password(self, value):
		if value:
			return make_password(value)
		return value

	def create(self, validated_data):
		return Customer.objects.create(**validated_data)


