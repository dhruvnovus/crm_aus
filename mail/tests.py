from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.test import override_settings
from employee.models import Employee
from django.utils import timezone
from task.models import Task


@override_settings(
    DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
    MIGRATION_MODULES={'lead': None}
)
class MailApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.employee = Employee.objects.create(first_name='Jane', last_name='Doe', email='jane@example.com', password='x')
        self.client.force_authenticate(user=self.employee)

    def test_mail_crud_and_create_task(self):
        # compose mail (draft)
        payload = {
            'from_email': 'sales@company.com',
            'to_emails': ['client@example.com'],
            'cc_emails': [],
            'bcc_emails': [],
            'subject': 'Product Demo Request - Enterprise Plan',
            'body': 'Hi team, I would like to schedule a product demo...',
            'employee_id': self.employee.id,
        }
        res = self.client.post('/api/mails/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.content)
        mail_id = res.data['id']

        # list
        res = self.client.get('/api/mails/?employee_id='+str(self.employee.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(res.data['count'], 1)

        # retrieve
        res = self.client.get(f'/api/mails/{mail_id}/?employee_id='+str(self.employee.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['subject'], payload['subject'])

        # create task from mail
        task_payload = {
            'title': payload['subject'],
            'assigned_to': self.employee.id,
            'due_date': str(timezone.localdate()),
            'due_time': timezone.now().strftime('%H:%M:%S'),
            'priority': 'medium',
            'employee_id': self.employee.id,
        }
        res = self.client.post(f'/api/mails/{mail_id}/create_task/', task_payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.content)
        task_id = res.data['id']
        self.assertTrue(Task.objects.filter(id=task_id).exists())
        # retrieve mail again; linked_task is hidden in API for now
        res = self.client.get(f'/api/mails/{mail_id}/?employee_id='+str(self.employee.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)


