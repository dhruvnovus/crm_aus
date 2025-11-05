from django.test import TestCase
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User, Permission
from rest_framework.test import APIRequestFactory

from lead.serializers import LeadCreateUpdateSerializer
from lead.models import Lead
from customers.models import Customer
from employee.models import Employee


class LeadCustomerCreationTests(TestCase):
    def setUp(self):
        # Minimal employee to be referenced by serializer if needed
        self.employee = Employee.objects.create(
            first_name='Test',
            last_name='User',
            email='employee@example.com',
            password=make_password('password123'),
            account_type='super_admin',
            staff_type='employee',
        )

    def test_auto_create_customer_when_customer_id_missing(self):
        payload = {
            'title': 'mr',
            'first_name': 'John',
            'last_name': 'Doe',
            'company_name': 'ACME',
            'contact_number': '+16512611051',
            'email_address': 'auto-create@example.com',
            'address': '123 Main St',
            'event': 'Expo',
            'lead_type': 'exhibitor',
            'status': 'new',
            'intensity': 'cold',
            'opportunity_price': '100.00',
            'employee_id': self.employee.id,
            # omit customer_id to trigger auto-create
        }

        serializer = LeadCreateUpdateSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        lead = serializer.save()

        self.assertIsInstance(lead, Lead)
        # customer should be created and linked
        self.assertIsNotNone(lead.customer_id)
        customer = Customer.objects.get(id=lead.customer_id)
        self.assertEqual(customer.email, 'auto-create@example.com')
        self.assertEqual(customer.first_name, 'John')
        self.assertEqual(customer.company_name, 'ACME')

    def test_link_existing_customer_when_customer_id_provided(self):
        # Prepare existing customer
        existing = Customer.objects.create(
            first_name='Jane',
            last_name='Smith',
            company_name='Widgets Co',
            email='jane@example.com',
            password=make_password('x'),
            type='exhibitor',
        )

        payload = {
            'title': 'mrs',
            'first_name': 'Jane',
            'last_name': 'Smith',
            'company_name': 'Widgets Co',
            'contact_number': '+16512611052',
            'email_address': 'jane@example.com',
            'address': '456 High St',
            'event': 'Expo',
            'lead_type': 'exhibitor',
            'status': 'new',
            'intensity': 'cold',
            'opportunity_price': '50.00',
            'employee_id': self.employee.id,
            'customer_id': existing.id,
        }

        serializer = LeadCreateUpdateSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        lead = serializer.save()

        self.assertEqual(lead.customer_id, existing.id)
        

class LeadDuplicateEmailPermissionTests(TestCase):
    def setUp(self):
        # Minimal employee for payloads
        self.employee = Employee.objects.create(
            first_name='Emp',
            last_name='One',
            email='emp1@example.com',
            password=make_password('password123'),
            account_type='super_admin',
            staff_type='employee',
        )

        # An existing lead to collide with
        self.existing_customer = Customer.objects.create(
            first_name='Alice',
            last_name='Base',
            company_name='Base Co',
            email='dup@example.com',
            password=make_password('x'),
            type='exhibitor',
        )
        self.existing_lead = Lead.objects.create(
            title='mr',
            first_name='Alice',
            last_name='Base',
            company_name='Base Co',
            contact_number='+11111111111',
            email_address='dup@example.com',
            address='A',
            event='E',
            lead_type='exhibitor',
            status='new',
            intensity='cold',
            customer=self.existing_customer,
        )

        # Users
        self.normal_user = User.objects.create_user(username='normal', password='pass12345')
        self.priv_user = User.objects.create_user(username='priv', password='pass12345')
        perm = Permission.objects.get(codename='can_use_duplicate_lead_email')
        self.priv_user.user_permissions.add(perm)
        self.priv_user.save()

        self.factory = APIRequestFactory()

    def _request_with_user(self, user):
        req = self.factory.post('/leads/', {})
        req.user = user
        return req

    def test_create_duplicate_email_denied_without_permission(self):
        payload = {
            'title': 'mr',
            'first_name': 'Bob',
            'last_name': 'New',
            'company_name': 'New Co',
            'contact_number': '+12222222222',
            'email_address': 'dup@example.com',  # duplicate
            'address': 'Addr',
            'event': 'Expo',
            'lead_type': 'exhibitor',
            'status': 'new',
            'intensity': 'cold',
            'employee_id': self.employee.id,
        }

        serializer = LeadCreateUpdateSerializer(data=payload, context={'request': self._request_with_user(self.normal_user)})
        self.assertFalse(serializer.is_valid())
        self.assertIn('email_address', serializer.errors)

    def test_create_duplicate_email_allowed_with_permission(self):
        payload = {
            'title': 'mr',
            'first_name': 'Bob',
            'last_name': 'Priv',
            'company_name': 'Priv Co',
            'contact_number': '+13333333333',
            'email_address': 'dup@example.com',  # duplicate
            'address': 'Addr',
            'event': 'Expo',
            'lead_type': 'exhibitor',
            'status': 'new',
            'intensity': 'cold',
            'employee_id': self.employee.id,
        }

        serializer = LeadCreateUpdateSerializer(data=payload, context={'request': self._request_with_user(self.priv_user)})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        lead = serializer.save()
        self.assertIsInstance(lead, Lead)

    def test_update_to_duplicate_email_denied_without_permission(self):
        # another distinct lead we will update to duplicate email
        other = Lead.objects.create(
            title='mr',
            first_name='Other',
            last_name='Guy',
            company_name='Other Co',
            contact_number='+14444444444',
            email_address='unique@example.com',
            address='B',
            event='E',
            lead_type='exhibitor',
            status='new',
            intensity='cold',
        )

        serializer = LeadCreateUpdateSerializer(
            instance=other,
            data={'email_address': 'dup@example.com'},
            partial=True,
            context={'request': self._request_with_user(self.normal_user)}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('email_address', serializer.errors)

    def test_update_to_duplicate_email_allowed_with_permission(self):
        other = Lead.objects.create(
            title='mr',
            first_name='Other',
            last_name='Guy',
            company_name='Other Co',
            contact_number='+15555555555',
            email_address='unique2@example.com',
            address='B',
            event='E',
            lead_type='exhibitor',
            status='new',
            intensity='cold',
        )

        serializer = LeadCreateUpdateSerializer(
            instance=other,
            data={'email_address': 'dup@example.com'},
            partial=True,
            context={'request': self._request_with_user(self.priv_user)}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated = serializer.save()
        self.assertEqual(updated.email_address, 'dup@example.com')
from django.test import TestCase

# Create your tests here.
