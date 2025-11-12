"""
Notification views for managing user notifications
"""
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.contrib.auth.models import User
from django.http import StreamingHttpResponse
from .models import Notification
from .serializers import NotificationSerializer
from employee.models import Employee
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken
from .sse import publisher, event_stream
from .renderers import SSERenderer


@extend_schema_view(
    list=extend_schema(
        summary="List notifications",
        description="Get all notifications for the authenticated user (no pagination). Returns unread_count, total_notification_count, and notifications array.",
        tags=["Notifications"],
    ),
    retrieve=extend_schema(
        summary="Get notification details",
        description="Retrieve detailed information about a specific notification",
        tags=["Notifications"],
    ),
)
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for managing notifications
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None  # Disable pagination
    
    def get_authenticated_employee(self):
        """
        Get the Employee instance from the authenticated user.
        Handles both Employee instances (from EmployeeJWTAuthentication) 
        and User instances (from standard JWTAuthentication).
        """
        user = self.request.user
        
        # If user is already an Employee instance, return it
        if isinstance(user, Employee):
            return user
        
        # Try to extract user_id from JWT token first (most reliable)
        auth_header = self.request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            try:
                token = auth_header.split(' ')[1]
                untyped_token = UntypedToken(token)
                # Access payload correctly from UntypedToken
                user_id = getattr(untyped_token, 'payload', {}).get('user_id')
                if user_id:
                    # The user_id in token is for Django User, not Employee
                    # We need to find Employee by matching email
                    try:
                        django_user = User.objects.get(id=user_id)
                        # Find Employee by email (since login creates User with email as username)
                        employee = Employee.objects.filter(email=django_user.username, is_active=True).first()
                        if employee:
                            return employee
                        # Fallback: try by email field
                        employee = Employee.objects.filter(email=django_user.email, is_active=True).first()
                        if employee:
                            return employee
                    except User.DoesNotExist:
                        pass
            except (InvalidToken, IndexError, KeyError, Exception) as e:
                # Debug: print error if needed
                pass
        
        # Try to get Employee from user.id (if it's a Django User)
        if hasattr(user, 'id'):
            # If user is Django User, find Employee by email
            if hasattr(user, 'username'):
                employee = Employee.objects.filter(email=user.username, is_active=True).first()
                if employee:
                    return employee
            if hasattr(user, 'email'):
                employee = Employee.objects.filter(email=user.email, is_active=True).first()
                if employee:
                    return employee
            # Last resort: try direct ID match
            employee = Employee.objects.filter(id=user.id, is_active=True).first()
            if employee:
                return employee
        
        return None
    
    def get_queryset(self):
        """Return notifications for the authenticated user"""
        employee = self.get_authenticated_employee()
        if employee:
            queryset = Notification.objects.filter(user=employee)
            
            # Filter by read status
            is_read = self.request.query_params.get('is_read', None)
            if is_read is not None:
                is_read_bool = is_read.lower() == 'true'
                queryset = queryset.filter(is_read=is_read_bool)
            
            # Filter by notification type
            # Supports: 'lead_assignment', 'task_assignment', 'task_reminder'
            notification_type = self.request.query_params.get('type', None)
            if notification_type:
                queryset = queryset.filter(notification_type=notification_type)
            
            return queryset.order_by('-created_at')
        return Notification.objects.none()
    
    def list(self, request, *args, **kwargs):
        """
        List all notifications for the authenticated user without pagination.
        Returns unread_count, total_notification_count, and notifications array.
        """
        employee = self.get_authenticated_employee()
        if not employee:
            return Response({
                'unread_count': 0,
                'total_notification_count': 0,
                'notifications': []
            })
        
        queryset = self.get_queryset()
        
        # Calculate counts
        total_count = queryset.count()
        unread_count = queryset.filter(is_read=False).count()
        
        # Serialize all notifications
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            'unread_count': unread_count,
            'total_notification_count': total_count,
            'notifications': serializer.data
        })
    
    @extend_schema(
        summary="Get lead assignment notifications",
        description="Get all notifications for admin assigned leads (lead_assignment type)",
        tags=["Notifications"],
    )
    @action(detail=False, methods=['get'])
    def leads(self, request):
        """Get all lead assignment notifications"""
        employee = self.get_authenticated_employee()
        if employee:
            queryset = Notification.objects.filter(
                user=employee,
                notification_type='lead_assignment'
            ).order_by('-created_at')
            
            # Pagination
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        return Response([])
    
    @extend_schema(
        summary="Get task assignment notifications",
        description="Get all notifications for task assignments (task_assignment type)",
        tags=["Notifications"],
    )
    @action(detail=False, methods=['get'])
    def tasks(self, request):
        """Get all task assignment notifications"""
        employee = self.get_authenticated_employee()
        if employee:
            queryset = Notification.objects.filter(
                user=employee,
                notification_type='task_assignment'
            ).order_by('-created_at')
            
            # Pagination
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        return Response([])
    
    @extend_schema(
        summary="Get task reminder notifications",
        description="Get all notifications for task reminders (task_reminder type)",
        tags=["Notifications"],
    )
    @action(detail=False, methods=['get'])
    def reminders(self, request):
        """Get all task reminder notifications"""
        employee = self.get_authenticated_employee()
        if employee:
            queryset = Notification.objects.filter(
                user=employee,
                notification_type='task_reminder'
            ).order_by('-created_at')
            
            # Pagination
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        return Response([])
    
    @extend_schema(
        summary="Mark notification as read",
        description="Mark a notification as read",
        tags=["Notifications"],
    )
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """Mark a notification as read"""
        notification = self.get_object()
        notification.mark_as_read()
        return Response(NotificationSerializer(notification).data)
    
    @extend_schema(
        summary="Mark all notifications as read",
        description="Mark all notifications for the authenticated user as read",
        tags=["Notifications"],
    )
    @action(detail=False, methods=['post'])
    def mark_all_as_read(self, request):
        """Mark all notifications as read for the authenticated user"""
        employee = self.get_authenticated_employee()
        if employee:
            from django.utils import timezone
            updated = Notification.objects.filter(
                user=employee,
                is_read=False
            ).update(is_read=True, read_at=timezone.now())
            
            return Response({
                'message': f'{updated} notification(s) marked as read',
                'count': updated
            })
        return Response({'message': 'No notifications to mark as read', 'count': 0})
    
    @extend_schema(
        summary="Get unread count",
        description="Get the count of unread notifications for the authenticated user",
        tags=["Notifications"],
    )
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get count of unread notifications"""
        employee = self.get_authenticated_employee()
        if employee:
            count = Notification.objects.filter(user=employee, is_read=False).count()
            return Response({'count': count})
        return Response({'count': 0})
    
    @extend_schema(
        summary="Server-Sent Events stream for real-time notifications",
        description="Stream real-time notifications using Server-Sent Events (SSE). "
                    "Connect to this endpoint to receive notifications as they are created. "
                    "Requires authentication via JWT token in Authorization header or 'token' query parameter. "
                    "Note: EventSource API doesn't support custom headers, so use query parameter for browser clients.",
        tags=["Notifications"],
    )
    @action(
        detail=False,
        methods=['get'],
        url_path='stream',
        renderer_classes=[SSERenderer],
        permission_classes=[permissions.AllowAny],  # authenticate inside the action
    )
    def stream(self, request):
        """
        SSE endpoint for streaming real-time notifications.
        Requires authentication. Sends notifications when they are created.
        
        Authentication:
        - Via Authorization header: Bearer <token> (for non-browser clients)
        - Via query parameter: ?token=<jwt_token> (for browser EventSource API)
        """
        import logging
        logger = logging.getLogger(__name__)
        
        employee = None
        token = None
        
        # Try to get token from Authorization header first
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        # Fallback to query parameter if no Authorization header
        if not token:
            token = request.query_params.get('token')
        
        if token:
            try:
                untyped_token = UntypedToken(token)
                user_id = getattr(untyped_token, 'payload', {}).get('user_id')
                logger.debug(f"Stream: Resolving employee from Django User ID {user_id}")
                if user_id:
                    django_user = User.objects.get(id=user_id)
                    # Find Employee by email (since login creates User with email as username)
                    employee = Employee.objects.filter(email=django_user.username, is_active=True).first()
                    if not employee:
                        employee = Employee.objects.filter(email=django_user.email, is_active=True).first()
                    if not employee:
                        # Last resort: try direct ID match (in case Employee ID matches User ID)
                        employee = Employee.objects.filter(id=user_id, is_active=True).first()
                    if employee:
                        logger.info(f"Stream: Resolved Employee ID {employee.id} from Django User ID {user_id}")
                    else:
                        logger.warning(f"Stream: Could not resolve Employee from Django User ID {user_id} (email: {django_user.username or django_user.email})")
            except User.DoesNotExist:
                logger.warning(f"Stream: Django User with ID {user_id} not found")
            except Exception as e:
                logger.error(f"Stream: Error resolving employee from token: {str(e)}", exc_info=True)
        else:
            # Try ViewSet authentication as fallback
            employee = self.get_authenticated_employee()
            if employee:
                logger.info(f"Stream: Resolved Employee ID {employee.id} via ViewSet authentication")
        
        if not employee:
            return Response(
                {'error': 'Authentication required. Provide JWT token via Authorization header or ?token query parameter.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Subscribe to notification events using Employee ID
        employee_id = employee.id
        logger.info(f"Stream: Subscribing to notifications for Employee ID {employee_id}")
        event_queue = publisher.subscribe(employee_id)
        
        # Create SSE response
        response = StreamingHttpResponse(
            event_stream(employee_id, event_queue),
            content_type='text/event-stream; charset=utf-8'
        )
        
        # Set headers for SSE and Heroku compatibility
        response['Cache-Control'] = 'no-cache, no-transform'
        response['X-Accel-Buffering'] = 'no'  # Disable buffering in nginx/proxies
        response['Connection'] = 'keep-alive'
        # Heroku-specific: prevent router timeout by ensuring regular data flow
        response['X-Content-Type-Options'] = 'nosniff'
        
        return response

