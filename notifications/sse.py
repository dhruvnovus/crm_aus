"""
Server-Sent Events (SSE) support for real-time notifications
"""
import json
import queue
import threading
import time
from typing import Dict
from django.http import StreamingHttpResponse
from django.utils import timezone


class NotificationEventPublisher:
    """
    Simple in-memory pub-sub system for notification events.
    Uses per-user queues to deliver notifications via SSE.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._queues: Dict[int, queue.Queue] = {}
                    cls._instance._lock = threading.Lock()
        return cls._instance
    
    def subscribe(self, user_id: int) -> queue.Queue:
        """
        Subscribe a user to receive notification events.
        Returns a queue that will receive notification events.
        """
        with self._lock:
            if user_id not in self._queues:
                self._queues[user_id] = queue.Queue(maxsize=100)
            return self._queues[user_id]
    
    def unsubscribe(self, user_id: int):
        """
        Unsubscribe a user from notification events.
        """
        with self._lock:
            self._queues.pop(user_id, None)
    
    def publish(self, user_id: int, event_type: str, data: dict):
        """
        Publish a notification event to a specific user.
        
        Args:
            user_id: The ID of the user to receive the notification
            event_type: Type of event (e.g., 'notification')
            data: The notification data to send
        """
        event = {
            'type': event_type,
            'data': data,
            'timestamp': timezone.now().isoformat(),
        }
        
        with self._lock:
            if user_id in self._queues:
                try:
                    self._queues[user_id].put_nowait(event)
                    # Debug logging
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug(f"Published event to user_id={user_id}, event_type={event_type}, queue_size={self._queues[user_id].qsize()}")
                except queue.Full:
                    # If queue is full, remove oldest event and add new one
                    try:
                        self._queues[user_id].get_nowait()
                        self._queues[user_id].put_nowait(event)
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Queue full for user_id={user_id}, removed oldest event")
                    except queue.Empty:
                        pass
            else:
                # Log if user is not subscribed
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"User {user_id} is not subscribed to notification stream (no active SSE connection)")


# Global publisher instance
publisher = NotificationEventPublisher()


def format_sse_event(event_id: int, event_type: str, data: dict) -> str:
    """
    Format data as a Server-Sent Event.
    
    Args:
        event_id: Unique event ID
        event_type: Type of event
        data: Event data (will be JSON encoded)
    
    Returns:
        Formatted SSE string
    """
    lines = []
    
    # Event ID
    lines.append(f"id: {event_id}")
    
    # Event type
    if event_type:
        lines.append(f"event: {event_type}")
    
    # Data (must be JSON encoded)
    json_data = json.dumps(data, default=str)
    # Split data into multiple lines if needed (SSE spec requires data: prefix on each line)
    for line in json_data.split('\n'):
        lines.append(f"data: {line}")
    
    # Empty line to indicate end of event
    lines.append("")
    
    return "\n".join(lines) + "\n"


def event_stream(user_id: int, event_queue: queue.Queue):
    """
    Generator function that yields SSE formatted events from the queue.
    
    Args:
        user_id: The user ID this stream is for
        event_queue: Queue to receive events from
    
    Yields:
        SSE formatted strings
    """
    event_id = 0
    
    # Send initial connection message
    yield format_sse_event(
        event_id=event_id,
        event_type='connected',
        data={'message': 'Connected to notification stream', 'user_id': user_id}
    )
    event_id += 1
    
    # Keep-alive ping every 5 seconds
    last_ping = time.time()
    PING_INTERVAL = 5
    
    while True:
        try:
            # Check for events with timeout to allow periodic pings
            try:
                event = event_queue.get(timeout=1)
                # Immediately format and yield the event when received
                yield format_sse_event(
                    event_id=event_id,
                    event_type=event.get('type', 'notification'),
                    data=event.get('data', {})
                )
                event_id += 1
            except queue.Empty:
                # Send ping if interval has passed
                current_time = time.time()
                if current_time - last_ping >= PING_INTERVAL:
                    yield format_sse_event(
                        event_id=event_id,
                        event_type='ping',
                        data={'message': 'keep-alive'}
                    )
                    event_id += 1
                    last_ping = current_time
                continue
            
        except GeneratorExit:
            # Client disconnected
            publisher.unsubscribe(user_id)
            break
        except Exception as e:
            # Send error event
            yield format_sse_event(
                event_id=event_id,
                event_type='error',
                data={'error': str(e)}
            )
            event_id += 1
            break

