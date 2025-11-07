# Server-Sent Events (SSE) Notifications Usage

## Overview

The notification system supports real-time notifications via Server-Sent Events (SSE) for:
- **Assigned tasks** - When a task is assigned to a user
- **Assigned leads** - When a lead is assigned to a sales staff member
- **Task reminders** - When a task reminder is triggered

## Endpoint

**URL:** `/api/notifications/stream/`

**Method:** `GET`

**Authentication:**
- **Option 1:** JWT token in `Authorization` header: `Bearer <token>`
- **Option 2:** JWT token as query parameter: `?token=<token>` (Required for browser EventSource API)

## Browser Client Example

```javascript
// Get your JWT token (from login)
const token = localStorage.getItem('auth_token');

// Connect to SSE stream
const eventSource = new EventSource(
    `/api/notifications/stream/?token=${token}`
);

// Handle notification events
eventSource.addEventListener('notification', (event) => {
    const notification = JSON.parse(event.data);
    console.log('New notification:', notification);
    
    // Display notification to user
    showNotificationToast(notification);
    
    // Update notification count
    updateNotificationCount();
});

// Handle connection established
eventSource.addEventListener('connected', (event) => {
    const data = JSON.parse(event.data);
    console.log('Connected:', data.message);
});

// Handle keep-alive pings
eventSource.addEventListener('ping', (event) => {
    // Connection is alive
    console.log('Ping received');
});

// Handle errors
eventSource.onerror = (error) => {
    console.error('SSE connection error:', error);
    // Reconnect after 5 seconds
    setTimeout(() => {
        eventSource.close();
        // Reconnect logic here
    }, 5000);
};

// Close connection when done
// eventSource.close();
```

## Node.js/Fetch API Example

```javascript
async function connectToNotifications(token) {
    const response = await fetch('/api/notifications/stream/', {
        method: 'GET',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Accept': 'text/event-stream'
        }
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        let eventType = 'message';
        let data = '';

        for (const line of lines) {
            if (line.startsWith('event:')) {
                eventType = line.substring(6).trim();
            } else if (line.startsWith('data:')) {
                data += line.substring(5).trim();
            } else if (line === '') {
                // Process complete event
                if (data) {
                    const notification = JSON.parse(data);
                    handleNotification(notification);
                    data = '';
                }
            }
        }
    }
}
```

## Python Client Example

```python
import requests
import json

def stream_notifications(token):
    url = 'http://localhost:8000/api/notifications/stream/'
    headers = {'Authorization': f'Bearer {token}'}
    
    response = requests.get(url, headers=headers, stream=True)
    
    buffer = ''
    for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
        if chunk:
            buffer += chunk
            lines = buffer.split('\n')
            buffer = lines[-1]  # Keep incomplete line in buffer
            
            event_type = 'message'
            data = ''
            
            for line in lines[:-1]:
                if line.startswith('event:'):
                    event_type = line[6:].strip()
                elif line.startswith('data:'):
                    data += line[5:].strip()
                elif line == '':
                    if data:
                        notification = json.loads(data)
                        handle_notification(notification)
                        data = ''
```

## Notification Event Structure

Each notification event contains:

```json
{
    "id": 1,
    "user": 5,
    "notification_type": "task_assignment",
    "title": "Task Assigned: Complete project",
    "message": "Task \"Complete project\" has been assigned to you.",
    "lead_id": null,
    "task_id": 123,
    "reminder_id": null,
    "metadata": {
        "priority": "high",
        "due_date": "2024-01-15",
        "due_time": "17:00:00",
        "status": "to_do"
    },
    "task_data": {
        "id": 123,
        "title": "Complete project",
        "description": "Finish the project documentation",
        "priority": "high",
        "status": "to_do",
        "due_date": "2024-01-15",
        "due_time": "17:00:00"
    },
    "is_read": false,
    "read_at": null,
    "created_at": "2024-01-10T10:30:00Z",
    "updated_at": "2024-01-10T10:30:00Z"
}
```

## Event Types

- `connected` - Sent when client connects to the stream
- `notification` - Sent when a new notification is created
- `ping` - Sent every 30 seconds as keep-alive
- `error` - Sent when an error occurs

## Notification Types

1. **`task_assignment`** - Task assigned to user
   - Contains `task_id` and `task_data`

2. **`lead_assignment`** - Lead assigned to sales staff
   - Contains `lead_id` and `lead_data`

3. **`task_reminder`** - Task reminder triggered
   - Contains `task_id`, `reminder_id`, `task_data`, and `reminder_data`

## Best Practices

1. **Reconnection Logic:** Implement automatic reconnection on connection loss
2. **Error Handling:** Handle authentication errors and network issues gracefully
3. **Rate Limiting:** Don't reconnect too frequently to avoid server overload
4. **Cleanup:** Always close the connection when the component unmounts or user logs out
5. **Token Security:** When using query parameter, ensure HTTPS is used to protect the token

## Security Notes

- Tokens passed as query parameters are visible in browser history and server logs
- For production, consider using cookie-based authentication for SSE
- Always use HTTPS in production
- Token expiration is handled - invalid tokens will return 401 Unauthorized

