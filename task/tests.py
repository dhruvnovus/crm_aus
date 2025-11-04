from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from employee.models import Employee
from .models import Task, Subtask, TaskHistory
from django.utils import timezone
from django.test import override_settings


@override_settings(DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}})
class TaskApiFlowTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.employee = Employee.objects.create(
            first_name='John', last_name='Doe', email='john@example.com', password='x'
        )
        # authenticate as Employee (DRF will consider it authenticated)
        self.client.force_authenticate(user=self.employee)

    def test_task_flow_create_update_delete_history(self):
        # prepare two existing tasks to link as subtasks later
        t2 = Task.objects.create(
            title='Child 2', description='', assigned_to=self.employee,
            priority='low', status='to_do', due_date=timezone.localdate(), due_time=timezone.now().time()
        )
        t3 = Task.objects.create(
            title='Child 3', description='', assigned_to=self.employee,
            priority='low', status='to_do', due_date=timezone.localdate(), due_time=timezone.now().time()
        )

        # 1) create parent task with subtasks list as integers
        url = '/api/tasks/'
        payload = {
            'title': 'Parent',
            'description': 'Prepare summary',
            'assigned_to': self.employee.id,
            'priority': 'low',
            'status': 'to_do',
            'due_date': str(timezone.localdate()),
            'due_time': timezone.now().strftime('%H:%M:%S'),
            'subtasks': [t2.id, t3.id],
            'attachments': [],
            'reminders': [],
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.content)
        task_id = res.data['id']

        # 2) patch subtasks with dict form
        patch_payload = {'subtasks': [
            {'child_task': t2.id, 'sort_order': 1},
            {'child_task': t3.id, 'sort_order': 2},
        ]}
        res = self.client.patch(f'/api/tasks/{task_id}/', patch_payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.content)
        self.assertEqual(Subtask.objects.filter(parent_task_id=task_id).count(), 2)

        # 3) complete
        res = self.client.post(f'/api/tasks/{task_id}/complete/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'completed')

        # 4) history list should have at least 3 entries (create, update, status_change)
        res = self.client.get(f'/api/tasks/{task_id}/history/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res.data), 3)

        # 5) delete (soft)
        res = self.client.delete(f'/api/tasks/{task_id}/')
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(Task.objects.get(id=task_id).is_deleted)


