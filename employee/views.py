from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count
from django.http import Http404
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from .models import Employee, EmergencyContact, EmployeeHistory
from .serializers import (
    EmployeeListSerializer,
    EmployeeDetailSerializer,
    EmployeeCreateUpdateSerializer,
    EmployeeStatsSerializer,
    EmergencyContactSerializer,
    EmployeeHistorySerializer
)


class EmployeePagination(PageNumberPagination):
    """
    Custom pagination for employee list
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


@extend_schema_view(
    list=extend_schema(
        summary="List all employees",
        description="Get a paginated list of all employees with optional filtering",
        tags=["Employees"],
    ),
    create=extend_schema(
        summary="Create employee (generic)",
        description="Create a new employee with any account type",
        tags=["Employees"],
    ),
    retrieve=extend_schema(
        summary="Get employee details",
        description="Retrieve detailed information about a specific employee",
        tags=["Employees"],
    ),
    update=extend_schema(
        summary="Update employee (full)",
        description="Update all fields of an employee",
        tags=["Employees"],
    ),
    partial_update=extend_schema(
        summary="Update employee (partial)",
        description="Update specific fields of an employee",
        tags=["Employees"],
    ),
    destroy=extend_schema(
        summary="Delete employee",
        description="Delete an employee from the system",
        tags=["Employees"],
    ),
)
class EmployeeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Employee CRUD operations
    Provides: list, create, retrieve, update, partial_update, destroy
    """
    queryset = Employee.objects.all()
    pagination_class = EmployeePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['account_type', 'staff_type', 'is_active', 'is_resigned', 'gender']
    search_fields = ['first_name', 'last_name', 'email', 'position', 'mobile_no', 'address']
    ordering_fields = ['created_at', 'updated_at', 'first_name', 'last_name', 'email']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """
        Return appropriate serializer class based on action
        """
        if self.action == 'list':
            return EmployeeListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return EmployeeCreateUpdateSerializer
        else:
            return EmployeeDetailSerializer
    
    def get_queryset(self):
        """
        Optionally restricts the returned employees by filtering against
        query parameters in the URL.
        """
        queryset = Employee.objects.all()
        
        # Filter by account type if specified
        account_type = self.request.query_params.get('account_type', None)
        if account_type:
            queryset = queryset.filter(account_type=account_type)
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True, is_resigned=False)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False, is_resigned=False)
        elif status_filter == 'resigned':
            queryset = queryset.filter(is_resigned=True)
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        """
        List employees with optional filtering
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    # History endpoints
    @extend_schema(
        summary="List employee history entries",
        tags=["Employees"],
    )
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        employee = self.get_object()
        queryset = EmployeeHistory.objects.filter(employee=employee).order_by('-timestamp')
        page = self.paginate_queryset(queryset)
        serializer = EmployeeHistorySerializer(page or queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @extend_schema(
        summary="Create employee history entry",
        description="Manually create a history entry (optional)",
        tags=["Employees"],
    )
    @action(detail=True, methods=['post'])
    def add_history(self, request, pk=None):
        employee = self.get_object()
        data = request.data.copy()
        data['employee'] = employee.id
        serializer = EmployeeHistorySerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Delete employee history entry",
        tags=["Employees"],
    )
    @action(detail=False, methods=['delete'], url_path='history/(?P<history_id>[^/.]+)')
    def delete_history(self, request, history_id=None):
        try:
            entry = EmployeeHistory.objects.get(id=history_id)
            entry.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except EmployeeHistory.DoesNotExist:
            return Response({"error": "History entry not found."}, status=status.HTTP_404_NOT_FOUND)
    
    def create(self, request, *args, **kwargs):
        """
        Create a new employee
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()
        
        # Return detailed employee data
        detail_serializer = EmployeeDetailSerializer(employee)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        summary="Create Super Admin employee",
        description="Create a new Super Admin employee. The account_type is automatically set to 'super_admin'.",
        tags=["Employees"],
        examples=[
            OpenApiExample(
                "Super Admin Example",
                summary="Create Super Admin",
                description="Example of creating a Super Admin employee",
                value={
                    "staff_type": "employee",
                    "first_name": "John",
                    "last_name": "Doe",
                    "email": "john.doe@example.com",
                    "password": "securepassword123",
                    "gender": "male",
                    "position": "Manager",
                    "emergency_contacts": [
                        {
                            "name": "Jane Doe",
                            "relationship": "Spouse",
                            "phone": "+61412345679",
                            "email": "jane.doe@example.com",
                            "address": "123 Main St, Sydney, NSW"
                        }
                    ]
                }
            )
        ]
    )
    @action(detail=False, methods=['post'])
    def add_super_admin(self, request):
        """
        Create a new Super Admin employee
        """
        # Automatically set account_type to super_admin
        data = request.data.copy()
        data['account_type'] = 'super_admin'
        
        serializer = EmployeeCreateUpdateSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()
        
        # Return detailed employee data
        detail_serializer = EmployeeDetailSerializer(employee)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        summary="Create Sales Staff employee",
        description="Create a new Sales Staff employee. The account_type is automatically set to 'sales_staff'.",
        tags=["Employees"],
        examples=[
            OpenApiExample(
                "Sales Staff Example",
                summary="Create Sales Staff",
                description="Example of creating a Sales Staff employee",
                value={
                    "staff_type": "employee",
                    "first_name": "Jane",
                    "last_name": "Smith",
                    "email": "jane.smith@example.com",
                    "password": "securepassword123",
                    "gender": "female",
                    "position": "Sales Representative",
                    "emergency_contacts": [
                        {
                            "name": "Bob Smith",
                            "relationship": "Father",
                            "phone": "+61412345680",
                            "email": "bob.smith@example.com",
                            "address": "456 Family St, Melbourne, VIC"
                        }
                    ]
                }
            )
        ]
    )
    @action(detail=False, methods=['post'])
    def add_sales_staff(self, request):
        """
        Create a new Sales Staff employee
        """
        # Automatically set account_type to sales_staff
        data = request.data.copy()
        data['account_type'] = 'sales_staff'
        
        serializer = EmployeeCreateUpdateSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()
        
        # Return detailed employee data
        detail_serializer = EmployeeDetailSerializer(employee)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)
    
    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a specific employee
        """
        instance = self.get_object()
        # log read
        try:
            EmployeeHistory.objects.create(
                employee=instance,
                action='read',
                changed_by=getattr(request, 'user', None),
                changes={}
            )
        except Exception:
            pass
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def update(self, request, *args, **kwargs):
        """
        Update an employee (full update)
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()
        
        # Return detailed employee data
        detail_serializer = EmployeeDetailSerializer(employee)
        return Response(detail_serializer.data)
    
    def partial_update(self, request, *args, **kwargs):
        """
        Partially update an employee
        """
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """
        Delete an employee
        """
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @extend_schema(
        summary="Get employee statistics",
        description="Get comprehensive statistics about employees",
        tags=["Employees"],
    )
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get employee statistics
        """
        queryset = self.get_queryset()
        
        stats = {
            'total_employees': queryset.count(),
            'active_employees': queryset.filter(is_active=True, is_resigned=False).count(),
            'inactive_employees': queryset.filter(is_active=False, is_resigned=False).count(),
            'resigned_employees': queryset.filter(is_resigned=True).count(),
            'super_admin_count': queryset.filter(account_type='super_admin').count(),
            'sales_staff_count': queryset.filter(account_type='sales_staff').count(),
            'employee_count': queryset.filter(staff_type='employee').count(),
            'contractor_count': queryset.filter(staff_type='contractor').count(),
        }
        
        serializer = EmployeeStatsSerializer(stats)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Get Super Admin employees",
        description="Get all Super Admin employees",
        tags=["Employees"],
    )
    @action(detail=False, methods=['get'])
    def super_admins(self, request):
        """
        Get all Super Admin employees
        """
        queryset = self.get_queryset().filter(account_type='super_admin')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Get Sales Staff employees",
        description="Get all Sales Staff employees",
        tags=["Employees"],
    )
    @action(detail=False, methods=['get'])
    def sales_staff(self, request):
        """
        Get all Sales Staff employees
        """
        queryset = self.get_queryset().filter(account_type='sales_staff')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Toggle employee status",
        description="Toggle the active status of an employee",
        tags=["Employees"],
    )
    @action(detail=True, methods=['post'])
    def toggle_status(self, request, pk=None):
        """
        Toggle employee active status
        """
        employee = self.get_object()
        employee.is_active = not employee.is_active
        employee.save()
        
        serializer = EmployeeDetailSerializer(employee)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Mark employee as resigned",
        description="Mark an employee as resigned",
        tags=["Employees"],
    )
    @action(detail=True, methods=['post'])
    def mark_resigned(self, request, pk=None):
        """
        Mark employee as resigned
        """
        employee = self.get_object()
        employee.is_resigned = True
        employee.is_active = False
        employee.save()
        
        serializer = EmployeeDetailSerializer(employee)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Get employee emergency contacts",
        description="Get all emergency contacts for a specific employee",
        tags=["Employees"],
    )
    @action(detail=True, methods=['get'])
    def emergency_contacts(self, request, pk=None):
        """
        Get emergency contacts for an employee
        """
        employee = self.get_object()
        contacts = employee.emergency_contacts.all()
        
        serializer = EmergencyContactSerializer(contacts, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Add emergency contact to employee",
        description="Add a new emergency contact for a specific employee",
        tags=["Employees"],
    )
    @action(detail=True, methods=['post'])
    def add_emergency_contact(self, request, pk=None):
        """
        Add emergency contact for an employee
        """
        employee = self.get_object()
        
        # Check if employee already has maximum emergency contacts
        if employee.emergency_contacts.count() >= 5:
            return Response(
                {"error": "Maximum 5 emergency contacts allowed per employee."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = EmergencyContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(employee=employee)
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        summary="Update employee emergency contact",
        description="Update an existing emergency contact for a specific employee",
        tags=["Employees"],
    )
    @action(detail=True, methods=['put'])
    def update_emergency_contact(self, request, pk=None):
        """
        Update a specific emergency contact for an employee
        """
        employee = self.get_object()
        contact_id = request.data.get('contact_id')
        
        if not contact_id:
            return Response(
                {"error": "contact_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            contact = employee.emergency_contacts.get(id=contact_id)
        except EmergencyContact.DoesNotExist:
            return Response(
                {"error": "Emergency contact not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = EmergencyContactSerializer(contact, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(serializer.data)
    
    @extend_schema(
        summary="Remove employee emergency contact",
        description="Remove an emergency contact from a specific employee",
        tags=["Employees"],
    )
    @action(detail=True, methods=['delete'])
    def remove_emergency_contact(self, request, pk=None):
        """
        Remove a specific emergency contact for an employee
        """
        employee = self.get_object()
        contact_id = request.data.get('contact_id')
        
        if not contact_id:
            return Response(
                {"error": "contact_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            contact = employee.emergency_contacts.get(id=contact_id)
            contact.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except EmergencyContact.DoesNotExist:
            return Response(
                {"error": "Emergency contact not found."},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @extend_schema(
        summary="Get all emergency contacts",
        description="Get all emergency contacts across all employees with filtering",
        tags=["Employees"],
    )
    @action(detail=False, methods=['get'])
    def all_emergency_contacts(self, request):
        """
        Get all emergency contacts across all employees
        """
        queryset = EmergencyContact.objects.select_related('employee')
        
        # Apply filters
        employee_id = request.query_params.get('employee_id', None)
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        
        relationship = request.query_params.get('relationship', None)
        if relationship:
            queryset = queryset.filter(relationship=relationship)
        
        # Apply search
        search = request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(phone__icontains=search) |
                Q(email__icontains=search) |
                Q(employee__first_name__icontains=search) |
                Q(employee__last_name__icontains=search)
            )
        
        # Apply ordering
        ordering = request.query_params.get('ordering', 'name')
        if ordering:
            queryset = queryset.order_by(ordering)
        
        serializer = EmergencyContactSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Get emergency contact by ID",
        description="Get a specific emergency contact by its ID",
        tags=["Employees"],
    )
    @action(detail=False, methods=['get'], url_path='emergency-contacts/(?P<contact_id>[^/.]+)')
    def get_emergency_contact(self, request, contact_id=None):
        """
        Get a specific emergency contact by ID
        """
        try:
            contact = EmergencyContact.objects.select_related('employee').get(id=contact_id)
            serializer = EmergencyContactSerializer(contact)
            return Response(serializer.data)
        except EmergencyContact.DoesNotExist:
            return Response(
                {"error": "Emergency contact not found."},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @extend_schema(
        summary="Update emergency contact by ID",
        description="Update a specific emergency contact by its ID",
        tags=["Employees"],
    )
    @action(detail=False, methods=['put'], url_path='emergency-contacts/(?P<contact_id>[^/.]+)')
    def update_emergency_contact_by_id(self, request, contact_id=None):
        """
        Update a specific emergency contact by ID
        """
        try:
            contact = EmergencyContact.objects.get(id=contact_id)
            serializer = EmergencyContactSerializer(contact, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        except EmergencyContact.DoesNotExist:
            return Response(
                {"error": "Emergency contact not found."},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @extend_schema(
        summary="Delete emergency contact by ID",
        description="Delete a specific emergency contact by its ID",
        tags=["Employees"],
    )
    @action(detail=False, methods=['delete'], url_path='emergency-contacts/(?P<contact_id>[^/.]+)')
    def delete_emergency_contact_by_id(self, request, contact_id=None):
        """
        Delete a specific emergency contact by ID
        """
        try:
            contact = EmergencyContact.objects.get(id=contact_id)
            contact.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except EmergencyContact.DoesNotExist:
            return Response(
                {"error": "Emergency contact not found."},
                status=status.HTTP_404_NOT_FOUND
            )
