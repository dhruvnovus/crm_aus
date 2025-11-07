from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    EmployeeViewSet,
    login_user,
    refresh_token,
    forgot_password,
    reset_password,
    change_password
)

# Create a router and register our viewsets with it
# Use default trailing_slash=True to accept URLs with trailing slashes
router = DefaultRouter(trailing_slash=True)
router.register(r'employees', EmployeeViewSet, basename='employee')

# Explicit route for emergency contacts by ID (maps to custom actions on the viewset)
employee_contact = EmployeeViewSet.as_view({
    'get': 'get_emergency_contact',
    'put': 'update_emergency_contact_by_id',
    'patch': 'update_emergency_contact_by_id',
    'delete': 'delete_emergency_contact_by_id',
})

# The API URLs are now determined automatically by the router
urlpatterns = [
    # Place explicit routes BEFORE router.urls to ensure they're matched first
    path('employees/emergency-contacts/<int:contact_id>/', employee_contact, name='employee-emergency-contact'),
    path('employees/emergency-contacts/<int:contact_id>', employee_contact, name='employee-emergency-contact-no-slash'),
    
    # Router URLs (includes all ViewSet routes)
    path('', include(router.urls)),
    
    # Authentication URLs
    path('login/', login_user, name='login'),
    path('refresh-token/', refresh_token, name='refresh-token'),
    path('forgot-password/', forgot_password, name='forgot-password'),
    path('reset-password/', reset_password, name='reset-password'),
    path('change-password/', change_password, name='change-password'),
]
