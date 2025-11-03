"""
Custom middleware to handle API URLs without trailing slashes
This adds trailing slashes to API routes before URL resolution to avoid 301 redirects
"""
from django.utils.deprecation import MiddlewareMixin


class APITrailingSlashMiddleware(MiddlewareMixin):
    """
    Middleware to add trailing slashes to API routes before URL resolution.
    This prevents 301 redirects by modifying the path before it's processed.
    """
    
    def process_request(self, request):
        # Only process API routes that don't have trailing slashes
        path_info = request.META.get('PATH_INFO', request.path_info)
        
        # Check if it's an API route and doesn't already have a trailing slash
        if path_info.startswith('/api/') and not path_info.endswith('/'):
            # Don't add slash if it's a file extension or format suffix
            last_segment = path_info.split('/')[-1]
            if '.' not in last_segment and last_segment:
                # Add trailing slash to the path_info
                new_path = path_info + '/'
                request.META['PATH_INFO'] = new_path
                request.path_info = new_path

