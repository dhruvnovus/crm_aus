from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    EmployeeViewSet,
    login_user,
    forgot_password,
    reset_password,
    change_password
)

# Create a router and register our viewsets with it
# Use default trailing_slash=True to accept URLs with trailing slashes
router = DefaultRouter(trailing_slash=True)
router.register(r'employees', EmployeeViewSet, basename='employee')

# The API URLs are now determined automatically by the router
urlpatterns = [
    path('', include(router.urls)),
    
    # Authentication URLs
    path('login/', login_user, name='login'),
    path('forgot-password/', forgot_password, name='forgot-password'),
    path('reset-password/', reset_password, name='reset-password'),
    path('change-password/', change_password, name='change-password'),
]
