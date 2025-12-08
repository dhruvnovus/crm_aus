"""
Simple SSE implementation for task reminders (no Redis required)
Uses queue-based approach for reliable event delivery
"""
import json
import queue
import threading
import time
import logging
from typing import Dict
from django.http import StreamingHttpResponse
from django.utils import timezone

logger = logging.getLogger("dea_crm")

# Store event queues per user
# Format: {user_id: queue.Queue}
USER_QUEUES: Dict[int, queue.Queue] = {}
QUEUES_LOCK = threading.Lock()


def stream_generator(user_id: int):
    """
    Generator function that yields SSE formatted events from the user's queue.
    Keeps connection alive and sends events when available.
    """
    # Send initial connection message
    yield f"data: {json.dumps({'type': 'connected', 'message': 'Connected to reminder stream', 'user_id': user_id})}\n\n"
    
    # Send all DUE reminders for this user when connection is established
    # Only send reminders that are due (remind_at <= now), not future ones
    try:
        from task.models import TaskReminder
        
        now = timezone.now()
        
        # Find all DUE reminders (remind_at <= current_time) for tasks assigned to this user
        # Future reminders will be sent by the scheduler when their time arrives
        # Note: We filter by status here because we only want to send reminders for active tasks
        # But the scheduler will handle this - we just send what's due
        due_reminders = TaskReminder.objects.filter(
            task__assigned_to_id=user_id,
            remind_at__lte=now,  # Only reminders that are due now or past
            is_sent=False,
            task__is_deleted=False,
            task__status__in=['to_do', 'in_progress', 'on_hold']  # Only active tasks
        ).select_related('task').order_by('remind_at')
        
        reminder_count = due_reminders.count()
        logger.info(f'Found {reminder_count} due reminders for user {user_id} (remind_at <= {now})')
        
        for reminder in due_reminders:
            task = reminder.task
            payload = {
                "type": "reminder",
                "task_id": task.id,
                "task_title": task.title,
                "task_description": task.description or "",
                "reminder_id": reminder.id,
                "remind_at": reminder.remind_at.strftime("%Y-%m-%d %H:%M:%S"),
                "remind_at_iso": reminder.remind_at.isoformat(),
                "due_date": str(task.due_date),
                "due_time": str(task.due_time),
                "priority": task.priority,
            }
            # Send as SSE event
            event_data = f"event: reminder\ndata: {json.dumps(payload)}\n\n"
            yield event_data
            logger.info(f'Sent due reminder {reminder.id} to user {user_id} via SSE')
    except Exception as e:
        logger.error(f'Error sending due reminders for user {user_id}: {str(e)}', exc_info=True)
    
    # Get or create queue for this user
    user_queue = get_user_queue(user_id)
    
    # Keep connection alive with periodic pings
    ping_counter = 0
    last_ping = time.time()
    PING_INTERVAL = 30  # Send ping every 30 seconds
    
    while True:
        try:
            # Check for events in queue (with timeout for periodic pings)
            try:
                event_data = user_queue.get(timeout=1)
                # Yield the event
                yield event_data
            except queue.Empty:
                # No event, send keep-alive ping if needed
                current_time = time.time()
                if current_time - last_ping >= PING_INTERVAL:
                    yield f": ping {ping_counter}\n\n"
                    ping_counter += 1
                    last_ping = current_time
                continue
            
        except GeneratorExit:
            # Client disconnected
            logger.info(f'Client {user_id} disconnected from reminder stream')
            remove_user_queue(user_id)
            break
        except Exception as e:
            logger.error(f'Error in stream_generator for user {user_id}: {str(e)}', exc_info=True)
            remove_user_queue(user_id)
            break


def get_user_queue(user_id: int) -> queue.Queue:
    """Get or create a queue for a user"""
    with QUEUES_LOCK:
        if user_id not in USER_QUEUES:
            USER_QUEUES[user_id] = queue.Queue(maxsize=100)
            logger.info(f'Created event queue for user {user_id}')
        return USER_QUEUES[user_id]


def remove_user_queue(user_id: int):
    """Remove the queue for a user when they disconnect"""
    with QUEUES_LOCK:
        if user_id in USER_QUEUES:
            del USER_QUEUES[user_id]
            logger.info(f'Removed event queue for user {user_id}')


def send_reminder_sse_event(user_id: int, event_type: str, data: dict):
    """
    Send an SSE event to a user's queue.
    
    Args:
        user_id: The ID of the user to send the event to
        event_type: Type of event (e.g., 'reminder')
        data: The event data to send
    """
    with QUEUES_LOCK:
        if user_id not in USER_QUEUES:
            logger.debug(f'No active SSE connection for user {user_id}, event will be lost')
            return
        
        # Format SSE event
        event_data = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        
        # Add event to user's queue
        user_queue = USER_QUEUES[user_id]
        try:
            user_queue.put_nowait(event_data)
            logger.info(f'Sent reminder event to user {user_id}: {event_type}')
        except queue.Full:
            # Queue is full, remove oldest event and add new one
            try:
                user_queue.get_nowait()  # Remove oldest
                user_queue.put_nowait(event_data)  # Add new
                logger.warning(f'Queue full for user {user_id}, removed oldest event')
            except queue.Empty:
                pass


def sse_reminder_stream(request, user_id: int):
    """
    Create an SSE stream for a user.
    Returns a StreamingHttpResponse that keeps the connection open.
    """
    response = StreamingHttpResponse(
        stream_generator(user_id),
        content_type='text/event-stream; charset=utf-8'
    )
    
    # Set headers for SSE
    response['Cache-Control'] = 'no-cache, no-transform'
    response['X-Accel-Buffering'] = 'no'
    response['X-Content-Type-Options'] = 'nosniff'
    
    # Add CORS headers
    origin = request.META.get('HTTP_ORIGIN')
    if origin:
        response['Access-Control-Allow-Origin'] = origin
        response['Access-Control-Allow-Credentials'] = 'true'
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, Cache-Control'
    
    return response

