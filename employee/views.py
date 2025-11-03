from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count
from django.http import Http404
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from .models import Employee, EmergencyContact, EmployeeHistory, PasswordResetToken
from django.contrib.auth.models import User
from .serializers import (
    EmployeeListSerializer,
    EmployeeDetailSerializer,
    EmployeeCreateUpdateSerializer,
    EmployeeStatsSerializer,
    EmergencyContactSerializer,
    EmployeeHistorySerializer,
    UserLoginSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
    ChangePasswordSerializer,
    UserResponseSerializer,
    LoginResponseSerializer,
    AuthResponseSerializer,
    RegistrationResponseSerializer
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
        # Filter out deleted records by default
        queryset = Employee.objects.filter(is_deleted=False)
        
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
        queryset = EmployeeHistory.objects.filter(employee=employee, is_deleted=False).order_by('-timestamp')
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
            # Soft delete instead of hard delete
            if hasattr(entry, 'is_deleted'):
                EmployeeHistory.objects.filter(id=entry.id).update(is_deleted=True)
                return Response({"success": True, "message": "History entry deleted successfully"}, status=status.HTTP_200_OK)
            # Fallback if column not present
            entry.delete()
            return Response({"success": True, "message": "History entry deleted"}, status=status.HTTP_200_OK)
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
        summary="Create Super Admin employee (Registration)",
        description="Create a new Super Admin employee with password. Acts as registration API.",
        tags=["Authentication"],
        request=EmployeeCreateUpdateSerializer,
        responses={
            201: RegistrationResponseSerializer,
            400: AuthResponseSerializer
        },
        examples=[
            OpenApiExample(
                "Super Admin Registration Example",
                summary="Create Super Admin",
                description="Example of creating a Super Admin employee with registration response",
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
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def add_super_admin(self, request):
        """
        Create a new Super Admin employee (Registration)
        """
        # Automatically set account_type to super_admin
        data = request.data.copy()
        data['account_type'] = 'super_admin'
        
        serializer = EmployeeCreateUpdateSerializer(data=data)
        if serializer.is_valid():
            employee = serializer.save()
            
            # Create/sync Django auth user and issue JWT
            raw_password = request.data.get('password')
            user, created = User.objects.get_or_create(
                username=employee.email,
                defaults={
                    'email': employee.email,
                    'first_name': employee.first_name,
                    'last_name': employee.last_name,
                    'is_active': True,
                }
            )
            if raw_password:
                user.set_password(raw_password)
            user.is_active = True
            user.save()

            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token
            
            # Prepare registration response data
            response_data = {
                "success": True,
                "message": "Super Admin registration successful.",
                "data": UserResponseSerializer(employee).data
            }
            
            return Response(response_data, status=status.HTTP_201_CREATED)
        
        return Response({
            "success": False,
            "message": "Super Admin registration failed.",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Create Sales Staff employee (Registration)",
        description="Create a new Sales Staff employee with password. Acts as registration API.",
        tags=["Authentication"],
        request=EmployeeCreateUpdateSerializer,
        responses={
            201: RegistrationResponseSerializer,
            400: AuthResponseSerializer
        },
        examples=[
            OpenApiExample(
                "Sales Staff Registration Example",
                summary="Create Sales Staff",
                description="Example of creating a Sales Staff employee with registration response",
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
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def add_sales_staff(self, request):
        """
        Create a new Sales Staff employee (Registration)
        """
        # Automatically set account_type to sales_staff
        data = request.data.copy()
        data['account_type'] = 'sales_staff'
        
        serializer = EmployeeCreateUpdateSerializer(data=data)
        if serializer.is_valid():
            employee = serializer.save()
            
            # Create/sync Django auth user and issue JWT
            raw_password = request.data.get('password')
            user, created = User.objects.get_or_create(
                username=employee.email,
                defaults={
                    'email': employee.email,
                    'first_name': employee.first_name,
                    'last_name': employee.last_name,
                    'is_active': True,
                }
            )
            if raw_password:
                user.set_password(raw_password)
            user.is_active = True
            user.save()

            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token
            
            # Prepare registration response data
            response_data = {
                "success": True,
                "message": "Sales Staff registration successful.",
                "data": UserResponseSerializer(employee).data
            }
            
            return Response(response_data, status=status.HTTP_201_CREATED)
        
        return Response({
            "success": False,
            "message": "Sales Staff registration failed.",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
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
        Soft delete an employee (sets is_deleted=True instead of actually deleting)
        """
        try:
            instance = self.get_object()
            if hasattr(instance, 'is_deleted'):
                # Use queryset update to avoid model save hooks
                Employee.objects.filter(pk=instance.pk).update(is_deleted=True)
            else:
                # Fallback if column not present yet
                self.perform_destroy(instance)
            return Response({"success": True, "message": "Employee deleted successfully"}, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"success": False, "error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    
    
    @extend_schema(
        summary="Get employee statistics",
        description="Get comprehensive statistics about employees (excludes deleted records)",
        tags=["Employees"],
    )
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get employee statistics (excludes deleted records)
        """
        queryset = Employee.objects.filter(is_deleted=False)
        
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
        Get emergency contacts for an employee (excludes deleted records)
        """
        employee = self.get_object()
        contacts = employee.emergency_contacts.filter(is_deleted=False).order_by('-created_at')
        
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
        
        # Check if employee already has maximum emergency contacts (excluding deleted)
        if employee.emergency_contacts.filter(is_deleted=False).count() >= 5:
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
            contact = employee.emergency_contacts.filter(is_deleted=False).get(id=contact_id)
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
            contact = employee.emergency_contacts.filter(is_deleted=False).get(id=contact_id)
            contact.is_deleted = True
            contact.save()
            return Response(
                {"success": True, "message": "Emergency contact deleted successfully"},
                status=status.HTTP_200_OK
            )
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
        Get all emergency contacts across all employees (excludes deleted records by default)
        """
        # Filter out deleted records by default
        queryset = EmergencyContact.objects.filter(is_deleted=False).select_related('employee')
        
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
        
        # Apply ordering (default: latest first)
        ordering = request.query_params.get('ordering', '-created_at')
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
        Get a specific emergency contact by ID (excludes deleted records)
        """
        try:
            contact = EmergencyContact.objects.filter(is_deleted=False).select_related('employee').get(id=contact_id)
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
        Update a specific emergency contact by ID (cannot update deleted records)
        """
        try:
            contact = EmergencyContact.objects.filter(is_deleted=False).get(id=contact_id)
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
        Soft delete a specific emergency contact by ID (sets is_deleted=True instead of actually deleting)
        """
        try:
            contact = EmergencyContact.objects.filter(is_deleted=False).get(id=contact_id)
            contact.is_deleted = True
            contact.save()
            return Response(
                {"success": True, "message": "Emergency contact deleted successfully"},
                status=status.HTTP_200_OK
            )
        except EmergencyContact.DoesNotExist:
            return Response(
                {"error": "Emergency contact not found."},
                status=status.HTTP_404_NOT_FOUND
            )


# Authentication Views

@extend_schema(
    summary="User Login",
    description="Login with email and password to get JWT tokens",
    tags=["Authentication"],
    request=UserLoginSerializer,
    responses={
        200: LoginResponseSerializer,
        400: AuthResponseSerializer,
        401: AuthResponseSerializer
    },
    examples=[
        OpenApiExample(
            "Login Example",
            summary="User Login",
            description="Example of user login",
            value={
                "username": "john@example.com",
                "password": "Password123!",
                "remember_me": True,
                "forgot_password": False
            }
        )
    ],
    operation_id="login_user",
    methods=["POST"]
)
@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    """
    Login user and return JWT tokens
    """
    serializer = UserLoginSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['username']
        password = serializer.validated_data['password']
        
        # Authenticate employee
        try:
            employee = Employee.objects.get(email=email, is_active=True)
            if not employee.check_password(password):
                employee = None
        except Employee.DoesNotExist:
            employee = None
        if employee:
            # Ensure a corresponding Django auth user exists and is synced
            user, _ = User.objects.get_or_create(
                username=employee.email,
                defaults={
                    'email': employee.email,
                    'first_name': employee.first_name,
                    'last_name': employee.last_name,
                    'is_active': True,
                }
            )
            if not user.check_password(password):
                user.set_password(password)
                user.is_active = True
                user.save()

            # Generate JWT tokens for Django auth user
            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token
            
            # Prepare user data: include full employee details in response
            from .serializers import EmployeeDetailSerializer
            detail = EmployeeDetailSerializer(employee).data
            # Keep backward compatibility for clients expecting user_id
            detail["user_id"] = employee.id
            user_data = detail
            
            response_data = {
                "success": True,
                "message": "Login successful.",
                "token": str(access_token),
                "user": user_data
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            return Response({
                "success": False,
                "message": "Invalid credentials."
            }, status=status.HTTP_401_UNAUTHORIZED)
    
    return Response({
        "success": False,
        "message": "Login failed.",
        "errors": serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Forgot Password",
    description="Send password reset link to user's email",
    tags=["Authentication"],
    request=ForgotPasswordSerializer,
    responses={
        200: AuthResponseSerializer,
        400: AuthResponseSerializer,
        500: AuthResponseSerializer
    },
    examples=[
        OpenApiExample(
            "Forgot Password Example",
            summary="Forgot Password",
            description="Example of forgot password request",
            value={
                "email": "john@example.com"
            }
        )
    ]
)
@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    """
    Send password reset link to user's email
    """
    serializer = ForgotPasswordSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        
        try:
            employee = Employee.objects.get(email=email, is_active=True)
            
            # Create password reset token
            reset_token = PasswordResetToken.create_token(employee)
            
            # Send email with reset link
            reset_link = f"https://yourapp.com/reset-password?token={reset_token.token}"
            
            subject = "Password Reset Request"
            message = f"""Hello {employee.full_name},

We received a request to reset your password. Click the link below to set a new password:

{reset_link}

If you didn't request a password reset, please ignore this email.

Thank you,
YourApp Support Team"""
            
            try:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [employee.email],
                    fail_silently=False,
                )
                
                return Response({
                    "success": True,
                    "message": "Password reset link sent to your email address."
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                return Response({
                    "success": False,
                    "message": "Failed to send email. Please try again later."
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Employee.DoesNotExist:
            # Don't reveal if email exists or not for security
            return Response({
                "success": True,
                "message": "Password reset link sent to your email address."
            }, status=status.HTTP_200_OK)
    
    return Response({
        "success": False,
        "message": "Invalid request.",
        "errors": serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Reset Password",
    description="Reset password using token from email",
    tags=["Authentication"],
    request=ResetPasswordSerializer,
    responses={
        200: AuthResponseSerializer,
        400: AuthResponseSerializer
    },
    examples=[
        OpenApiExample(
            "Reset Password Example",
            summary="Reset Password",
            description="Example of password reset",
            value={
                "token": "abc123xyz",
                "new_password": "NewPassword123!",
                "confirm_password": "NewPassword123!"
            }
        )
    ]
)
@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """
    Reset password using token
    """
    serializer = ResetPasswordSerializer(data=request.data)
    if serializer.is_valid():
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']
        
        try:
            reset_token = PasswordResetToken.objects.get(token=token)
            if reset_token.is_valid():
                # Update employee password
                employee = reset_token.employee
                employee.set_password(new_password)
                
                # Mark token as used
                reset_token.is_used = True
                reset_token.save()
                
                return Response({
                    "success": True,
                    "message": "Password has been reset successfully."
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "success": False,
                    "message": "Invalid or expired token."
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except PasswordResetToken.DoesNotExist:
            return Response({
                "success": False,
                "message": "Invalid token."
            }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response({
        "success": False,
        "message": "Password reset failed.",
        "errors": serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Change Password",
    description="Change password for authenticated user",
    tags=["Authentication"],
    request=ChangePasswordSerializer,
    responses={
        200: AuthResponseSerializer,
        400: AuthResponseSerializer,
        404: AuthResponseSerializer
    },
    examples=[
        OpenApiExample(
            "Change Password Example",
            summary="Change Password",
            description="Example of changing password",
            value={
                "current_password": "OldPass123!",
                "new_password": "NewPass123!",
                "retype_new_password": "NewPass123!"
            }
        )
    ]
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change password for authenticated user
    """
    serializer = ChangePasswordSerializer(data=request.data)
    if serializer.is_valid():
        current_password = serializer.validated_data['current_password']
        new_password = serializer.validated_data['new_password']

        # Resolve the authenticated Django User robustly
        auth_user = None
        try:
            # Most common: TokenUser/User with id
            user_id = getattr(request.user, 'id', None) or getattr(request.user, 'user_id', None)
            if user_id:
                auth_user = User.objects.filter(id=user_id).first()
            # Fallbacks
            if not auth_user:
                username = getattr(request.user, 'username', None)
                if username:
                    auth_user = User.objects.filter(username=username).first()
            if not auth_user:
                email = getattr(request.user, 'email', None)
                if email:
                    auth_user = User.objects.filter(email=email).first()
        except Exception:
            auth_user = None

        if not auth_user:
            return Response({
                "success": False,
                "message": "Authenticated user not found."
            }, status=status.HTTP_404_NOT_FOUND)

        # Verify current password
        if not auth_user.check_password(current_password):
            return Response({
                "success": False,
                "message": "Current password is incorrect."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Update Django user password
        try:
            auth_user.set_password(new_password)
            auth_user.save()
        except Exception:
            return Response({
                "success": False,
                "message": "Failed to update password."
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Sync Employee password (by email)
        try:
            if auth_user.email:
                employee = Employee.objects.filter(email=auth_user.email).first()
                if employee:
                    employee.set_password(new_password)
        except Exception:
            # Ignore sync errors; core password already changed
            pass

        return Response({
            "success": True,
            "message": "Password changed successfully."
        }, status=status.HTTP_200_OK)
    
    return Response({
        "success": False,
        "message": "Password change failed.",
        "errors": serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)
