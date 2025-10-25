from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Sum
from django.http import Http404
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from .models import Lead, LeadHistory
from .serializers import (
    LeadListSerializer,
    LeadDetailSerializer,
    LeadCreateUpdateSerializer,
    LeadStatsSerializer,
    LeadBulkImportSerializer,
    LeadHistorySerializer
)


class LeadPagination(PageNumberPagination):
    """
    Custom pagination for lead list
    """
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 500


@extend_schema_view(
    list=extend_schema(
        summary="List all leads",
        description="Get a paginated list of all leads with optional filtering",
        tags=["Leads"],
    ),
    create=extend_schema(
        summary="Create lead",
        description="Create a new lead",
        tags=["Leads"],
    ),
    retrieve=extend_schema(
        summary="Get lead details",
        description="Retrieve detailed information about a specific lead",
        tags=["Leads"],
    ),
    update=extend_schema(
        summary="Update lead (full)",
        description="Update all fields of a lead",
        tags=["Leads"],
    ),
    partial_update=extend_schema(
        summary="Update lead (partial)",
        description="Update specific fields of a lead",
        tags=["Leads"],
    ),
    destroy=extend_schema(
        summary="Delete lead",
        description="Delete a lead from the system",
        tags=["Leads"],
    ),
)
class LeadViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Lead CRUD operations
    Provides: list, create, retrieve, update, partial_update, destroy
    """
    queryset = Lead.objects.all()
    pagination_class = LeadPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'lead_type', 'intensity', 'assigned_sales_staff', 'event']
    search_fields = ['first_name', 'last_name', 'company_name', 'email_address', 'contact_number', 'tags']
    ordering_fields = ['date_received', 'created_at', 'updated_at', 'first_name', 'last_name', 'company_name', 'opportunity_price']
    ordering = ['-date_received']
    
    def get_serializer_class(self):
        """
        Return appropriate serializer class based on action
        """
        if self.action == 'list':
            return LeadListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return LeadCreateUpdateSerializer
        else:
            return LeadDetailSerializer
    
    def get_queryset(self):
        """
        Optionally restricts the returned leads by filtering against
        query parameters in the URL.
        """
        queryset = Lead.objects.all()
        
        # Filter by status category
        status_category = self.request.query_params.get('status_category', None)
        if status_category:
            if status_category == 'active':
                queryset = queryset.exclude(status__in=['lost', 'withdrawn'])
            elif status_category == 'inactive':
                queryset = queryset.filter(status__in=['lost', 'withdrawn'])
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        """
        List leads with optional filtering
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        """
        Create a new lead
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lead = serializer.save()
        
        # Return detailed lead data
        detail_serializer = LeadDetailSerializer(lead)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)
    
    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a specific lead
        """
        instance = self.get_object()
        # log read
        try:
            LeadHistory.objects.create(
                lead=instance,
                action='read',
                changed_by=None,
                changes={}
            )
        except Exception:
            pass
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def update(self, request, *args, **kwargs):
        """
        Update a lead (full update)
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        lead = serializer.save()
        
        # Return detailed lead data
        detail_serializer = LeadDetailSerializer(lead)
        return Response(detail_serializer.data)
    
    def partial_update(self, request, *args, **kwargs):
        """
        Partially update a lead
        """
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """
        Delete a lead
        """
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @extend_schema(
        summary="Get lead statistics",
        description="Get comprehensive statistics about leads",
        tags=["Leads"],
    )
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get lead statistics
        """
        queryset = self.get_queryset()
        
        stats = {
            'total_leads': queryset.count(),
            'new_leads': queryset.filter(status='new').count(),
            'info_pack_leads': queryset.filter(status='info_pack').count(),
            'attempted_contact_leads': queryset.filter(status='attempted_contact').count(),
            'contacted_leads': queryset.filter(status='contacted').count(),
            'contract_invoice_sent_leads': queryset.filter(status='contract_invoice_sent').count(),
            'contract_signed_paid_leads': queryset.filter(status='contract_signed_paid').count(),
            'withdrawn_leads': queryset.filter(status='withdrawn').count(),
            'lost_leads': queryset.filter(status='lost').count(),
            'converted_leads': queryset.filter(status='converted').count(),
            'future_leads': queryset.filter(status='future').count(),
            'total_opportunity_value': queryset.aggregate(
                total=Sum('opportunity_price')
            )['total'] or 0,
            'exhibitor_count': queryset.filter(lead_type='exhibitor').count(),
            'sponsor_count': queryset.filter(lead_type='sponsor').count(),
            'visitor_count': queryset.filter(lead_type='visitor').count(),
        }
        
        serializer = LeadStatsSerializer(stats)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Get leads by status",
        description="Get leads filtered by specific status",
        tags=["Leads"],
    )
    @action(detail=False, methods=['get'])
    def by_status(self, request):
        """
        Get leads by specific status
        """
        status_param = request.query_params.get('status', 'new')
        queryset = self.get_queryset().filter(status=status_param)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Get new leads",
        description="Get all new leads",
        tags=["Leads"],
    )
    @action(detail=False, methods=['get'])
    def new_leads(self, request):
        """
        Get all new leads
        """
        queryset = self.get_queryset().filter(status='new')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Get lost leads",
        description="Get all lost leads",
        tags=["Leads"],
    )
    @action(detail=False, methods=['get'])
    def lost_leads(self, request):
        """
        Get all lost leads
        """
        queryset = self.get_queryset().filter(status='lost')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Get converted leads",
        description="Get all converted leads",
        tags=["Leads"],
    )
    @action(detail=False, methods=['get'])
    def converted_leads(self, request):
        """
        Get all converted leads
        """
        queryset = self.get_queryset().filter(status='converted')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Get future leads",
        description="Get all future leads",
        tags=["Leads"],
    )
    @action(detail=False, methods=['get'])
    def future_leads(self, request):
        """
        Get all future leads
        """
        queryset = self.get_queryset().filter(status='future')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Update lead status",
        description="Update the status of a specific lead",
        tags=["Leads"],
    )
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """
        Update lead status
        """
        lead = self.get_object()
        new_status = request.data.get('status')
        
        if not new_status:
            return Response(
                {"error": "Status is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if new_status not in [choice[0] for choice in Lead.STATUS_CHOICES]:
            return Response(
                {"error": "Invalid status."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        lead.status = new_status
        lead.save()
        
        serializer = LeadDetailSerializer(lead)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Assign lead to sales staff",
        description="Assign a lead to a specific sales staff member",
        tags=["Leads"],
    )
    @action(detail=True, methods=['post'])
    def assign_sales_staff(self, request, pk=None):
        """
        Assign lead to sales staff
        """
        lead = self.get_object()
        sales_staff = request.data.get('assigned_sales_staff')
        
        if not sales_staff:
            return Response(
                {"error": "Sales staff assignment is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        lead.assigned_sales_staff = sales_staff
        lead.save()
        
        serializer = LeadDetailSerializer(lead)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Bulk import leads",
        description="Import multiple leads at once",
        tags=["Leads"],
        examples=[
            OpenApiExample(
                "Bulk Import Example",
                summary="Import multiple leads",
                description="Example of importing multiple leads",
                value={
                    "leads_data": [
                        {
                            "title": "mr",
                            "first_name": "John",
                            "last_name": "Doe",
                            "company_name": "Example Company",
                            "contact_number": "+61412345678",
                            "email_address": "john.doe@example.com",
                            "lead_type": "exhibitor",
                            "status": "new",
                            "event": "Aged & Disability Expo Newcastle"
                        },
                        {
                            "title": "mrs",
                            "first_name": "Jane",
                            "last_name": "Smith",
                            "company_name": "Another Company",
                            "contact_number": "+61412345679",
                            "email_address": "jane.smith@example.com",
                            "lead_type": "sponsor",
                            "status": "new",
                            "event": "Aged & Disability Expo Sydney"
                        }
                    ]
                }
            )
        ]
    )
    @action(detail=False, methods=['post'])
    def bulk_import(self, request):
        """
        Bulk import leads
        """
        serializer = LeadBulkImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        leads_data = serializer.validated_data['leads_data']
        created_leads = []
        errors = []
        
        for lead_data in leads_data:
            try:
                lead_serializer = LeadCreateUpdateSerializer(data=lead_data)
                if lead_serializer.is_valid():
                    lead = lead_serializer.save()
                    created_leads.append(lead)
                else:
                    errors.append({
                        'data': lead_data,
                        'errors': lead_serializer.errors
                    })
            except Exception as e:
                errors.append({
                    'data': lead_data,
                    'errors': str(e)
                })
        
        response_data = {
            'created_count': len(created_leads),
            'error_count': len(errors),
            'created_leads': LeadDetailSerializer(created_leads, many=True).data,
            'errors': errors
        }
        
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        summary="Export leads",
        description="Export leads to CSV format",
        tags=["Leads"],
    )
    @action(detail=False, methods=['get'])
    def export(self, request):
        """
        Export leads to CSV
        """
        import csv
        from django.http import HttpResponse
        
        queryset = self.filter_queryset(self.get_queryset())
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="leads_export.csv"'
        
        writer = csv.writer(response)
        
        # Write header
        writer.writerow([
            'ID', 'Title', 'First Name', 'Last Name', 'Company Name',
            'Contact Number', 'Email Address', 'Custom Email Addresses',
            'Address', 'Event', 'Lead Type', 'Booth Size', 'Sponsorship Type',
            'Registration Groups', 'Status', 'Intensity', 'Opportunity Price',
            'Tags', 'How Did You Hear', 'Reason for Enquiry',
            'Assigned Sales Staff', 'Date Received', 'Created At', 'Updated At'
        ])
        
        # Write data
        for lead in queryset:
            writer.writerow([
                lead.id, lead.get_title_display(), lead.first_name, lead.last_name,
                lead.company_name, lead.contact_number, lead.email_address,
                lead.custom_email_addresses, lead.address, lead.event,
                lead.get_lead_type_display(), lead.booth_size, lead.sponsorship_type,
                lead.registration_groups, lead.get_status_display(),
                lead.get_intensity_display(), lead.opportunity_price, lead.tags,
                lead.how_did_you_hear, lead.reason_for_enquiry, lead.assigned_sales_staff,
                lead.date_received, lead.created_at, lead.updated_at
            ])
        
        return response

    # History endpoints
    @extend_schema(
        summary="List lead history entries",
        tags=["Leads"],
    )
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        lead = self.get_object()
        queryset = LeadHistory.objects.filter(lead=lead).order_by('-timestamp')
        page = self.paginate_queryset(queryset)
        serializer = LeadHistorySerializer(page or queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @extend_schema(
        summary="Create lead history entry",
        description="Manually create a history entry (optional)",
        tags=["Leads"],
    )
    @action(detail=True, methods=['post'])
    def add_history(self, request, pk=None):
        lead = self.get_object()
        data = request.data.copy()
        data['lead'] = lead.id
        serializer = LeadHistorySerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Delete lead history entry",
        tags=["Leads"],
    )
    @action(detail=False, methods=['delete'], url_path='history/(?P<history_id>[^/.]+)')
    def delete_history(self, request, history_id=None):
        try:
            entry = LeadHistory.objects.get(id=history_id)
            entry.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except LeadHistory.DoesNotExist:
            return Response({"error": "History entry not found."}, status=status.HTTP_404_NOT_FOUND)