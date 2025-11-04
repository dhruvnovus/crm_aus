import logging
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework import viewsets, status, filters
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.db import IntegrityError
from .models import Customer
from .serializers import CustomerSerializer, CustomerCreateSerializer
from drf_spectacular.utils import extend_schema, extend_schema_view

class CustomerPagination(PageNumberPagination):
    """
    Custom pagination for customer list
    """
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 500

# App logger
logger = logging.getLogger('crm_aus')

@extend_schema_view(
	list=extend_schema(
		summary="List all customers",
		description="Get a paginated list of all customers with optional filtering",
		tags=["Customers"],
	),
)
@extend_schema_view(
	create=extend_schema(
		summary="Create a new customer",
		description="Create a new customer",
		tags=["Customers"],
	),
	retrieve=extend_schema(
		summary="Get a customer by ID",
		description="Get a customer by ID",
		tags=["Customers"],
	),
	update=extend_schema(
		summary="Update a customer",
		description="Update a customer",
		tags=["Customers"],
	),
	partial_update=extend_schema(
		summary="Partial update a customer",
		description="Partial update a customer",
		tags=["Customers"],
	),
    destroy=extend_schema(
		summary="Delete a customer",
		description="Delete a customer",
		tags=["Customers"],
	),
)

class CustomerViewSet(viewsets.ModelViewSet):
	queryset = Customer.objects.all().order_by('-created_at')
	pagination_class = CustomerPagination
	filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
	filterset_fields = ['type', 'event']
	search_fields = ['first_name', 'last_name', 'company_name', 'email']
	ordering_fields = ['created_at', 'updated_at', 'first_name', 'last_name', 'company_name', 'email']
	ordering = ['-created_at']
	permission_classes = [IsAuthenticated]

	@staticmethod
	def _first_error(errors):
		try:
			first = next(iter(errors.values()))
			while isinstance(first, (list, tuple)) and first:
				first = first[0]
			if isinstance(first, dict):
				first = next(iter(first.values()))
			return str(first)
		except Exception:
			return "Invalid data"

	def get_serializer_class(self):
		if self.action in ['create', 'update', 'partial_update']:
			return CustomerCreateSerializer
		return CustomerSerializer

	def get_queryset(self):
		# Exclude soft-deleted records by default
		return Customer.objects.filter(is_deleted=False).order_by('-created_at')

	def list(self, request, *args, **kwargs):
		queryset = self.filter_queryset(self.get_queryset())
		page = self.paginate_queryset(queryset)
		if page is not None:
			serializer = self.get_serializer(page, many=True)
			return self.get_paginated_response(serializer.data)
		serializer = self.get_serializer(queryset, many=True)
		return Response(serializer.data)

	def create(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data)
		if not serializer.is_valid():
			return Response({"status": False, "error": self._first_error(serializer.errors)}, status=status.HTTP_400_BAD_REQUEST)
		try:
			customer = serializer.save()
			# Use read serializer for output
			data = CustomerSerializer(customer).data
			return Response({"status": True, "message": "Customer created successfully", "data": data}, status=status.HTTP_201_CREATED)
		except IntegrityError:
			return Response({"status": False, "error": "Email already exists."}, status=status.HTTP_400_BAD_REQUEST)
		except Exception as exc:
			return Response({"status": False, "error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

	def update(self, request, *args, **kwargs):
		partial = kwargs.pop('partial', False)
		instance = self.get_object()
		serializer = self.get_serializer(instance, data=request.data, partial=partial)
		if not serializer.is_valid():
			return Response({"status": False, "error": self._first_error(serializer.errors)}, status=status.HTTP_400_BAD_REQUEST)
		try:
			customer = serializer.save()
		except Exception as exc:
			return Response({"status": False, "error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
		return Response({"status": True, "message": "Customer updated successfully", "data": serializer.data})
	
	def partial_update(self, request, *args, **kwargs):
		kwargs['partial'] = True
		return self.update(request, *args, **kwargs)
	
	def destroy(self, request, *args, **kwargs):	
		try:
			instance = self.get_object()
			if hasattr(instance, 'is_deleted'):
				Customer.objects.filter(pk=instance.pk).update(is_deleted=True)
			else:
				self.perform_destroy(instance)
			return Response({"status": True, "message": "Customer deleted successfully"}, status=status.HTTP_200_OK)
		except Exception as exc:
			return Response({"status": False, "error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

