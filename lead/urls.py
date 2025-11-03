from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LeadViewSet, RegistrationGroupViewSet, LeadTagViewSet, SponsorshipTypeViewSet

# Create a router and register our viewsets with it
router = DefaultRouter(trailing_slash=False)
router.register(r'leads', LeadViewSet, basename='lead')
router.register(r'registration-groups', RegistrationGroupViewSet, basename='registration-group')
router.register(r'lead-tags', LeadTagViewSet, basename='lead-tag')
router.register(r'sponsorship-types', SponsorshipTypeViewSet, basename='sponsorship-type')

# The API URLs are now determined automatically by the router
urlpatterns = [
    path('', include(router.urls)),
]
