"""
Server-Sent Events (SSE) support for real-time notifications
"""
import json
import queue
import threading
import time
import os
from typing import Dict, Optional
from django.http import StreamingHttpResponse
from django.utils import timezone

# Try to import Redis, fall back to in-memory if not available
_redis_available = False
_redis_client = None
_redis_pubsub = None

try:
    import redis
    # Try to connect to Redis (check for Heroku Redis URL or default)
    redis_url = os.getenv('REDIS_URL') or os.getenv('REDISCLOUD_URL') or 'redis://localhost:6379/0'
    try:
        _redis_client = redis.from_url(redis_url, decode_responses=True)
        # Test connection
        _redis_client.ping()
        _redis_available = True
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Redis connected successfully for notification pub-sub")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Redis not available, falling back to in-memory pub-sub: {str(e)}")
        _redis_available = False
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("Redis package not installed, falling back to in-memory pub-sub")


class NotificationEventPublisher:
    """
    Hybrid pub-sub system for notification events.
    Uses Redis pub-sub when available (for multi-worker production),
    falls back to in-memory queues for single-process development.
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
                    cls._instance._use_redis = _redis_available
                    cls._instance._redis_client = _redis_client
        return cls._instance
    
    def subscribe(self, user_id: int) -> queue.Queue:
        """
        Subscribe a user to receive notification events.
        Returns a queue that will receive notification events.
        """
        if self._use_redis and self._redis_client:
            # For Redis, we still use a local queue to receive messages from Redis subscriber
            with self._lock:
                if user_id not in self._queues:
                    self._queues[user_id] = queue.Queue(maxsize=100)
                    # Start Redis subscriber thread for this user
                    self._start_redis_subscriber(user_id)
            return self._queues[user_id]
        else:
            # In-memory queue
            with self._lock:
                if user_id not in self._queues:
                    self._queues[user_id] = queue.Queue(maxsize=100)
            return self._queues[user_id]
    
    def _start_redis_subscriber(self, user_id: int):
        """Start a background thread to subscribe to Redis channel for this user"""
        def redis_subscriber():
            # Create a separate Redis connection for subscriber (required for pubsub)
            redis_url = os.getenv('REDIS_URL') or os.getenv('REDISCLOUD_URL') or 'redis://localhost:6379/0'
            try:
                subscriber_client = redis.from_url(redis_url, decode_responses=True)
                pubsub = subscriber_client.pubsub()
                channel = f"notifications:user:{user_id}"
                pubsub.subscribe(channel)
                
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Redis subscriber started for user_id={user_id}, channel={channel}")
                
                for message in pubsub.listen():
                    if message['type'] == 'message':
                        try:
                            event_data = json.loads(message['data'])
                            # Put event into local queue
                            with self._lock:
                                if user_id in self._queues:
                                    try:
                                        self._queues[user_id].put_nowait(event_data)
                                    except queue.Full:
                                        # Remove oldest if full
                                        try:
                                            self._queues[user_id].get_nowait()
                                            self._queues[user_id].put_nowait(event_data)
                                        except queue.Empty:
                                            pass
                        except Exception as e:
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.error(f"Error processing Redis message for user_id={user_id}: {str(e)}", exc_info=True)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Redis subscriber error for user_id={user_id}: {str(e)}", exc_info=True)
            finally:
                try:
                    pubsub.close()
                    subscriber_client.close()
                except:
                    pass
        
        # Start subscriber thread
        thread = threading.Thread(target=redis_subscriber, daemon=True)
        thread.start()
    
    def unsubscribe(self, user_id: int):
        """
        Unsubscribe a user from notification events.
        """
        with self._lock:
            self._queues.pop(user_id, None)
            # Note: Redis subscription will be cleaned up when thread exits
    
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
        
        if self._use_redis and self._redis_client:
            # Publish to Redis channel
            try:
                channel = f"notifications:user:{user_id}"
                self._redis_client.publish(channel, json.dumps(event))
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Published event to Redis channel={channel}, event_type={event_type}")
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to publish to Redis for user_id={user_id}: {str(e)}", exc_info=True)
        else:
            # In-memory publish
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


def format_sse_event(event_id: int, event_type: str, data: dict, retry_ms: int | None = None) -> str:
    """
    Format data as a Server-Sent Event.
    
    Args:
        event_id: Unique event ID
        event_type: Type of event
        data: Event data (will be JSON encoded)
        retry_ms: Optional reconnection time for clients (in milliseconds)
    
    Returns:
        Formatted SSE string
    """
    lines = []
    
    # Event ID
    lines.append(f"id: {event_id}")
    
    # Event type
    if event_type:
        lines.append(f"event: {event_type}")
    
    # Optional retry directive (client reconnection delay)
    if retry_ms is not None:
        lines.append(f"retry: {retry_ms}")
    
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
    initial_event = format_sse_event(
        event_id=event_id,
        event_type='connected',
        data={'message': 'Connected to notification stream', 'user_id': user_id},
        retry_ms=3000,  # advise clients to retry after 3s if disconnected
    )
    yield initial_event
    event_id += 1
    
    # Keep-alive ping every 30 seconds (Heroku router timeout is 55s, so we stay well under)
    last_ping = time.time()
    PING_INTERVAL = 30
    # Separate lightweight heartbeat (comment) every 20 seconds to defeat buffering proxies
    last_heartbeat = time.time()
    HEARTBEAT_INTERVAL = 20
    
    while True:
        try:
            # Check for events with timeout to allow periodic pings
            try:
                event = event_queue.get(timeout=1)
                # Immediately format and yield the event when received
                event_data = format_sse_event(
                    event_id=event_id,
                    event_type=event.get('type', 'notification'),
                    data=event.get('data', {}),
                    retry_ms=3000,
                )
                yield event_data
                event_id += 1
            except queue.Empty:
                # Send ping if interval has passed
                current_time = time.time()
                if current_time - last_ping >= PING_INTERVAL:
                    ping_data = format_sse_event(
                        event_id=event_id,
                        event_type='ping',
                        data={'message': 'keep-alive', 'timestamp': current_time},
                        retry_ms=3000,
                    )
                    yield ping_data
                    event_id += 1
                    last_ping = current_time
                
                # Send lightweight heartbeat comment to force flush on some proxies
                if current_time - last_heartbeat >= HEARTBEAT_INTERVAL:
                    # Comment lines in SSE start with ":" and end with double newline
                    # They are ignored by clients but keep the connection active and bypass buffering
                    heartbeat = f": heartbeat {int(current_time)}\n\n"
                    yield heartbeat
                    last_heartbeat = current_time
                continue
            
        except GeneratorExit:
            # Client disconnected
            publisher.unsubscribe(user_id)
            break
        except Exception as e:
            # Send error event
            error_data = format_sse_event(
                event_id=event_id,
                event_type='error',
                data={'error': str(e)},
                retry_ms=3000,
            )
            yield error_data
            event_id += 1
            break

