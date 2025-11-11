from rest_framework.renderers import BaseRenderer


class SSERenderer(BaseRenderer):
    """
    Minimal renderer to satisfy DRF content negotiation for Server-Sent Events.
    We return a StreamingHttpResponse directly in the view, so render() won't be used.
    """
    media_type = 'text/event-stream'
    format = 'event-stream'
    charset = 'utf-8'
    render_style = 'text'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        # DRF won't call this when we return StreamingHttpResponse, but implement for completeness
        if data is None:
            return b""
        if isinstance(data, bytes):
            return data
        return str(data).encode(self.charset or 'utf-8')


