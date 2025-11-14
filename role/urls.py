from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RoleViewSet, PermissionViewSet

# Create a router and register our viewsets with it
router = DefaultRouter(trailing_slash=True)
router.register(r'roles', RoleViewSet, basename='role')
router.register(r'permissions', PermissionViewSet, basename='permission')

urlpatterns = [
    path('', include(router.urls)),
]