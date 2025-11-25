from django.db import models
from django.core.validators import RegexValidator


class Customer(models.Model):
	TYPE_CHOICES = [
		('exhibitor', 'Exhibitor'),
		('sponsor', 'Sponsor'),
	]
	SECONDARY_MOBILE_TYPE_CHOICES = [
		('technical contact', 'Technical Contact'),
		('financial contact', 'Financial Contact'),
		('hr contact', 'HR Contact'),
		('support contact', 'Support Contact'),
		('sales contact', 'Sales Contact'),
		('additional contact', 'Additional Contact'),
	]

	first_name = models.CharField(max_length=100)
	last_name = models.CharField(max_length=100)
	company_name = models.CharField(max_length=200)
	company_logo = models.TextField(blank=True, null=True, help_text='Base64 image string')
	# Primary mobile number
	mobile_phone = models.CharField(
		max_length=20,
		blank=True,
		null=True,
		validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be in format '+999999999'. Up to 15 digits allowed.")],
	)
	mobile_phone_code = models.CharField(max_length=10, blank=True, null=True)
	# Secondary mobile numbers
	secondary_mobile_numbers = models.JSONField(
		default=list,
		blank=True,
		null=True,
		help_text="List of secondary mobile numbers (E.164 strings)"
	)
	secondary_mobile_phone_code = models.JSONField(
		default=list,
		blank=True,
		null=True,
		help_text="Country codes aligned with each secondary mobile number"
	)
	secondary_mobile_type = models.JSONField(
		choices=SECONDARY_MOBILE_TYPE_CHOICES,
		default=list,
		blank=True,
		null=True,
		help_text="List of secondary mobile types"
	)
	email = models.EmailField(unique=True)
	address = models.TextField(blank=True, null=True)
	abn_no = models.CharField(max_length=20, blank=True, null=True)
	position = models.CharField(max_length=100, blank=True, null=True)
	password = models.CharField(max_length=128)
	type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='exhibitor')
	event = models.CharField(max_length=200, blank=True, null=True)
	is_deleted = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-created_at']
		db_table = 'customers'

	def __str__(self) -> str:
		return f"{self.first_name} {self.last_name} - {self.company_name}"
