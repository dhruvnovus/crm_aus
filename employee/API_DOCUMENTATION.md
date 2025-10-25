# Employee Management API Documentation

## Overview
This API provides comprehensive CRUD operations for employee management in the CRM system. It supports two account types: **Super Admin** and **Sales Staff**.

## Base URL
```
http://localhost:8000/api/
```

## Authentication
Currently, the API does not require authentication. In production, you should implement proper authentication mechanisms.

## Account Types
- `super_admin`: Super Admin employees with full system access
- `sales_staff`: Sales Staff employees with limited access

## API Endpoints (Unified Employee & Emergency Contact API)

The system provides a single unified API for both employee and emergency contact management. Two separate database tables are maintained with a foreign key relationship, but all operations are handled through the employee API endpoints.

### 1. List Employees
**GET** `/api/employees/`

Returns a paginated list of all employees.

**Query Parameters:**
- `page`: Page number (default: 1)
- `page_size`: Number of items per page (default: 10, max: 100)
- `account_type`: Filter by account type (`super_admin` or `sales_staff`)
- `staff_type`: Filter by staff type (`employee` or `contractor`)
- `is_active`: Filter by active status (true/false)
- `is_resigned`: Filter by resignation status (true/false)
- `gender`: Filter by gender (`male`, `female`, `other`)
- `status`: Filter by status (`active`, `inactive`, `resigned`)
- `search`: Search in first_name, last_name, email, position, mobile_no, address
- `ordering`: Order by field (prefix with `-` for descending)

**Example Request:**
```
GET /api/employees/?account_type=super_admin&status=active&search=john&ordering=-created_at
```

**Response:**
```json
{
    "count": 25,
    "next": "http://localhost:8000/api/employees/?page=2",
    "previous": null,
    "results": [
        {
            "id": 1,
            "account_type": "super_admin",
            "account_type_display": "Super Admin",
            "staff_type": "employee",
            "staff_type_display": "Employee",
            "is_active": true,
            "is_resigned": false,
            "title": "mr",
            "first_name": "John",
            "last_name": "Doe",
            "full_name": "John Doe",
            "email": "john.doe@example.com",
            "position": "Manager",
            "gender": "male",
            "mobile_no": "+61412345678",
            "address": "123 Main St, Sydney, NSW",
            "post_code": "2000",
            "profile_image": null,
            "hours_per_week": 40,
            "status_display": "Active",
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T10:30:00Z"
        }
    ]
}
```

### 2. Create Employee (Generic)
**POST** `/api/employees/`

Creates a new employee with any account type.

**Request Body:**
```json
{
    "account_type": "super_admin",
    "staff_type": "employee",
    "is_active": true,
    "is_resigned": false,
    "title": "mr",
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com",
    "password": "securepassword123",
    "position": "Manager",
    "gender": "male",
    "date_of_birth": "1990-01-15",
    "mobile_no": "+61412345678",
    "landline_no": "+61298765432",
    "language_spoken": "English, Spanish",
    "unit_number": "Unit 5",
    "address": "123 Main St, Sydney, NSW",
    "post_code": "2000",
    "profile_image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k=",
    "admin_notes": "Internal notes about the employee",
    "hours_per_week": 40,
    "emergency_contacts": [
        {
            "name": "Jane Doe",
            "relationship": "Spouse",
            "phone": "+61412345679",
            "email": "jane.doe@example.com",
            "address": "123 Main St, Sydney, NSW"
        }
    ]
}
```

**Response:** Returns the created employee with full details (HTTP 201).

### 2a. Create Super Admin Employee
**POST** `/api/employees/add_super_admin/`

Creates a new Super Admin employee. The `account_type` is automatically set to `super_admin`.

**Request Body:**
```json
{
    "staff_type": "employee",
    "is_active": true,
    "is_resigned": false,
    "title": "mr",
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com",
    "password": "securepassword123",
    "position": "Manager",
    "gender": "male",
    "date_of_birth": "1990-01-15",
    "mobile_no": "+61412345678",
    "landline_no": "+61298765432",
    "language_spoken": "English, Spanish",
    "unit_number": "Unit 5",
    "address": "123 Main St, Sydney, NSW",
    "post_code": "2000",
    "profile_image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k=",
    "admin_notes": "Internal notes about the employee",
    "hours_per_week": 40,
    "emergency_contacts": [
        {
            "name": "Jane Doe",
            "relationship": "Spouse",
            "phone": "+61412345679",
            "email": "jane.doe@example.com",
            "address": "123 Main St, Sydney, NSW"
        }
    ]
}
```

**Response:** Returns the created Super Admin employee with full details (HTTP 201).

### 2b. Create Sales Staff Employee
**POST** `/api/employees/add_sales_staff/`

Creates a new Sales Staff employee. The `account_type` is automatically set to `sales_staff`.

**Request Body:**
```json
{
    "staff_type": "employee",
    "is_active": true,
    "is_resigned": false,
    "title": "mr",
    "first_name": "Jane",
    "last_name": "Smith",
    "email": "jane.smith@example.com",
    "password": "securepassword123",
    "position": "Sales Representative",
    "gender": "female",
    "date_of_birth": "1992-05-20",
    "mobile_no": "+61412345680",
    "landline_no": "+61298765433",
    "language_spoken": "English, French",
    "unit_number": "Unit 10",
    "address": "456 Sales St, Melbourne, VIC",
    "post_code": "3000",
    "profile_image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k=",
    "admin_notes": "Sales team member",
    "hours_per_week": 38,
    "emergency_contacts": [
        {
            "name": "Bob Smith",
            "relationship": "Father",
            "phone": "+61412345681",
            "email": "bob.smith@example.com",
            "address": "789 Family St, Brisbane, QLD"
        }
    ]
}
```

**Response:** Returns the created Sales Staff employee with full details (HTTP 201).

### 3. Retrieve Employee
**GET** `/api/employees/{id}/`

Returns detailed information about a specific employee.

**Response:**
```json
{
    "id": 1,
    "account_type": "super_admin",
    "account_type_display": "Super Admin",
    "staff_type": "employee",
    "staff_type_display": "Employee",
    "is_active": true,
    "is_resigned": false,
    "title": "mr",
    "title_display": "Mr",
    "first_name": "John",
    "last_name": "Doe",
    "full_name": "John Doe",
    "display_name": "Mr John Doe",
    "email": "john.doe@example.com",
    "position": "Manager",
    "gender": "male",
    "gender_display": "Male",
    "date_of_birth": "1990-01-15",
    "mobile_no": "+61412345678",
    "landline_no": "+61298765432",
    "language_spoken": "English, Spanish",
    "unit_number": "Unit 5",
    "address": "123 Main St, Sydney, NSW",
    "post_code": "2000",
    "profile_image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k=",
    "admin_notes": "Internal notes about the employee",
    "hours_per_week": 40,
    "status_display": "Active",
    "emergency_contacts": [
        {
            "id": 1,
            "name": "Jane Doe",
            "relationship": "Spouse",
            "phone": "+61412345679",
            "email": "jane.doe@example.com",
            "address": "123 Main St, Sydney, NSW",
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T10:30:00Z"
        }
    ],
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
}
```

### 4. Update Employee (Full Update)
**PUT** `/api/employees/{id}/`

Updates an employee with all fields.

**Request Body:** Same as create employee.

**Response:** Returns the updated employee with full details.

### 5. Update Employee (Partial Update)
**PATCH** `/api/employees/{id}/`

Updates specific fields of an employee.

**Request Body:**
```json
{
    "position": "Senior Manager",
    "mobile_no": "+61412345680",
    "admin_notes": "Promoted to Senior Manager"
}
```

**Response:** Returns the updated employee with full details.

### 6. Delete Employee
**DELETE** `/api/employees/{id}/`

Deletes an employee.

**Response:** HTTP 204 No Content

### 7. Employee Statistics
**GET** `/api/employees/stats/`

Returns statistics about employees.

**Response:**
```json
{
    "total_employees": 25,
    "active_employees": 20,
    "inactive_employees": 3,
    "resigned_employees": 2,
    "super_admin_count": 5,
    "sales_staff_count": 20,
    "employee_count": 22,
    "contractor_count": 3
}
```

### 8. List Super Admins
**GET** `/api/employees/super_admins/`

Returns a paginated list of Super Admin employees only.

**Query Parameters:** Same as list employees.

### 9. List Sales Staff
**GET** `/api/employees/sales_staff/`

Returns a paginated list of Sales Staff employees only.

**Query Parameters:** Same as list employees.

### 10. Toggle Employee Status
**POST** `/api/employees/{id}/toggle_status/`

Toggles the active status of an employee.

**Response:** Returns the updated employee details.

### 11. Mark Employee as Resigned
**POST** `/api/employees/{id}/mark_resigned/`

Marks an employee as resigned and sets them as inactive.

**Response:** Returns the updated employee details.

### 12. Get Emergency Contacts
**GET** `/api/employees/{id}/emergency_contacts/`

Returns emergency contacts for a specific employee.

**Response:**
```json
[
    {
        "id": 1,
        "name": "Jane Doe",
        "relationship": "Spouse",
        "phone": "+61412345679",
        "email": "jane.doe@example.com",
        "address": "123 Main St, Sydney, NSW",
        "created_at": "2024-01-15T10:30:00Z",
        "updated_at": "2024-01-15T10:30:00Z"
    }
]
```

### 13. Add Emergency Contact
**POST** `/api/employees/{id}/add_emergency_contact/`

Adds an emergency contact for an employee.

**Request Body:**
```json
{
    "name": "Jane Doe",
    "relationship": "Spouse",
    "phone": "+61412345679",
    "email": "jane.doe@example.com",
    "address": "123 Main St, Sydney, NSW"
}
```

**Response:** Returns the created emergency contact (HTTP 201).

**Error Response (HTTP 400):**
```json
{
    "error": "Maximum 5 emergency contacts allowed per employee."
}
```

### 14. Update Emergency Contact
**PUT** `/api/employees/{id}/update_emergency_contact/`

Updates a specific emergency contact for an employee.

**Request Body:**
```json
{
    "contact_id": 1,
    "name": "Jane Smith",
    "relationship": "Spouse",
    "phone": "+61412345680",
    "email": "jane.smith@example.com",
    "address": "456 New St, Melbourne, VIC"
}
```

**Response:** Returns the updated emergency contact.

### 15. Remove Emergency Contact
**DELETE** `/api/employees/{id}/remove_emergency_contact/`

Removes a specific emergency contact for an employee.

**Request Body:**
```json
{
    "contact_id": 1
}
```

**Response:** HTTP 204 No Content

## Emergency Contact Management (Unified API)

All emergency contact operations are now handled through the employee API endpoints. The system maintains two separate tables (Employee and EmergencyContact) with a foreign key relationship, but provides a unified API interface.

### 16. List All Emergency Contacts
**GET** `/api/employees/all_emergency_contacts/`

Returns a list of all emergency contacts across all employees.

**Query Parameters:**
- `employee_id`: Filter by specific employee ID
- `relationship`: Filter by relationship type
- `search`: Search in name, phone, email, employee names
- `ordering`: Order by field (name, created_at)

**Example Request:**
```
GET /api/employees/all_emergency_contacts/?employee_id=1&relationship=Spouse
```

**Response:**
```json
[
    {
        "id": 1,
        "name": "Jane Doe",
        "relationship": "Spouse",
        "phone": "+61412345679",
        "email": "jane.doe@example.com",
        "address": "123 Main St, Sydney, NSW",
        "created_at": "2024-01-15T10:30:00Z",
        "updated_at": "2024-01-15T10:30:00Z"
    }
]
```

### 17. Get Emergency Contact by ID
**GET** `/api/employees/emergency-contacts/{contact_id}/`

Returns details of a specific emergency contact.

**Response:**
```json
{
    "id": 1,
    "name": "Jane Doe",
    "relationship": "Spouse",
    "phone": "+61412345679",
    "email": "jane.doe@example.com",
    "address": "123 Main St, Sydney, NSW",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
}
```

### 18. Update Emergency Contact by ID
**PUT** `/api/employees/emergency-contacts/{contact_id}/`

Updates an emergency contact by its ID.

**Request Body:**
```json
{
    "name": "Jane Smith",
    "relationship": "Spouse",
    "phone": "+61412345682",
    "email": "jane.smith@example.com",
    "address": "456 Updated St, Melbourne, VIC"
}
```

**Response:** Returns the updated emergency contact.

### 19. Delete Emergency Contact by ID
**DELETE** `/api/employees/emergency-contacts/{contact_id}/`

Deletes an emergency contact by its ID.

**Response:** HTTP 204 No Content

## Base64 Image Handling

The system stores profile images as Base64 strings directly in the database instead of using file uploads. This approach provides several benefits:

- **Portability**: Images are stored with the data, making database backups complete
- **Simplicity**: No need for file system management or media URL configuration
- **Consistency**: All data is stored in the database

### Image Format Support
- **Supported formats**: JPEG, PNG, GIF, BMP
- **Maximum size**: Recommended 400x400px or smaller for optimal performance
- **Base64 format**: `data:image/jpeg;base64,<base64_string>` or just `<base64_string>`

### Example Base64 Image
```json
{
    "profile_image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k="
}
```

### Converting Images to Base64

#### JavaScript (Frontend)
```javascript
function convertToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => resolve(reader.result);
        reader.onerror = error => reject(error);
    });
}

// Usage
const fileInput = document.getElementById('profileImage');
const file = fileInput.files[0];
const base64String = await convertToBase64(file);
```

#### Python (Backend)
```python
import base64

def image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        return f"data:image/jpeg;base64,{encoded_string}"

# Usage
base64_image = image_to_base64("path/to/image.jpg")
```

## Field Descriptions

### Employee Fields
- `account_type`: Account type (super_admin, sales_staff)
- `staff_type`: Staff type (employee, contractor)
- `is_active`: Whether the employee is currently active
- `is_resigned`: Whether the employee has resigned
- `title`: Title (mr, mrs, miss, ms, other)
- `first_name`: Employee's first name (required)
- `last_name`: Employee's last name (required)
- `email`: Employee's email address (required, unique)
- `password`: Employee's password (required, write-only)
- `position`: Employee's position/title
- `gender`: Employee's gender (male, female, other)
- `date_of_birth`: Employee's date of birth (YYYY-MM-DD)
- `mobile_no`: Mobile phone number
- `landline_no`: Landline phone number
- `language_spoken`: Languages spoken by employee
- `unit_number`: Unit/Apartment number
- `address`: Employee's full address
- `post_code`: Postal code
- `profile_image`: Profile image as Base64 string
- `admin_notes`: Internal notes visible only to administrators
- `hours_per_week`: Weekly contracted hours

### Emergency Contact Fields
- `name`: Emergency contact's name (required)
- `relationship`: Relationship to employee (required)
- `phone`: Emergency contact's phone number (required)
- `email`: Emergency contact's email address
- `address`: Emergency contact's address

## Error Responses

### Validation Errors (HTTP 400)
```json
{
    "field_name": ["Error message"]
}
```

### Not Found (HTTP 404)
```json
{
    "detail": "Not found."
}
```

### Server Error (HTTP 500)
```json
{
    "detail": "A server error occurred."
}
```

## Setup Instructions

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create and run migrations:
```bash
python manage.py makemigrations employee
python manage.py migrate
```

3. Create a superuser (optional):
```bash
python manage.py createsuperuser
```

4. Run the development server:
```bash
python manage.py runserver
```

5. Access the API at: `http://localhost:8000/api/`
6. Access the admin interface at: `http://localhost:8000/admin/`

## Testing the API

You can test the API using:
- **Django REST Framework Browsable API**: Visit `http://localhost:8000/api/employees/`
- **Postman**: Import the endpoints and test with sample data
- **curl**: Use command line to test endpoints
- **Python requests**: Use the requests library to interact with the API

## Example curl Commands

### Create a Super Admin employee:
```bash
curl -X POST http://localhost:8000/api/employees/add_super_admin/ \
  -H "Content-Type: application/json" \
  -d '{
    "staff_type": "employee",
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com",
    "password": "securepassword123",
    "gender": "male",
    "position": "Manager",
    "profile_image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k=",
    "emergency_contacts": [
      {
        "name": "Jane Doe",
        "relationship": "Spouse",
        "phone": "+61412345679",
        "email": "jane.doe@example.com",
        "address": "123 Main St, Sydney, NSW"
      }
    ]
  }'
```

### Create a Sales Staff employee:
```bash
curl -X POST http://localhost:8000/api/employees/add_sales_staff/ \
  -H "Content-Type: application/json" \
  -d '{
    "staff_type": "employee",
    "first_name": "Jane",
    "last_name": "Smith",
    "email": "jane.smith@example.com",
    "password": "securepassword123",
    "gender": "female",
    "position": "Sales Representative",
    "profile_image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k=",
    "emergency_contacts": [
      {
        "name": "Bob Smith",
        "relationship": "Father",
        "phone": "+61412345680",
        "email": "bob.smith@example.com",
        "address": "456 Family St, Melbourne, VIC"
      }
    ]
  }'
```

### Create an employee with generic endpoint (requires account_type):
```bash
curl -X POST http://localhost:8000/api/employees/ \
  -H "Content-Type: application/json" \
  -d '{
    "account_type": "super_admin",
    "staff_type": "employee",
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com",
    "password": "securepassword123",
    "gender": "male",
    "emergency_contacts": [
      {
        "name": "Jane Doe",
        "relationship": "Spouse",
        "phone": "+61412345679",
        "email": "jane.doe@example.com",
        "address": "123 Main St, Sydney, NSW"
      }
    ]
  }'
```

### Get all employees:
```bash
curl http://localhost:8000/api/employees/
```

### Get employee statistics:
```bash
curl http://localhost:8000/api/employees/stats/
```

### Add emergency contact to existing employee:
```bash
curl -X POST http://localhost:8000/api/employees/1/add_emergency_contact/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Mary Johnson",
    "relationship": "Mother",
    "phone": "+61412345681",
    "email": "mary.johnson@example.com",
    "address": "789 Parent St, Brisbane, QLD"
  }'
```

### Update emergency contact:
```bash
curl -X PUT http://localhost:8000/api/employees/1/update_emergency_contact/ \
  -H "Content-Type: application/json" \
  -d '{
    "contact_id": 1,
    "name": "Jane Smith",
    "relationship": "Spouse",
    "phone": "+61412345682",
    "email": "jane.smith@example.com",
    "address": "123 Updated St, Sydney, NSW"
  }'
```

### Remove emergency contact:
```bash
curl -X DELETE http://localhost:8000/api/employees/1/remove_emergency_contact/ \
  -H "Content-Type: application/json" \
  -d '{
    "contact_id": 1
  }'
```

### Get all emergency contacts for an employee:
```bash
curl http://localhost:8000/api/employees/all_emergency_contacts/?employee_id=1
```

### Get all emergency contacts across all employees:
```bash
curl http://localhost:8000/api/employees/all_emergency_contacts/
```

### Get specific emergency contact by ID:
```bash
curl http://localhost:8000/api/employees/emergency-contacts/1/
```

### Update emergency contact by ID:
```bash
curl -X PUT http://localhost:8000/api/employees/emergency-contacts/1/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Jane Smith",
    "relationship": "Spouse",
    "phone": "+61412345682",
    "email": "jane.smith@example.com",
    "address": "456 Updated St, Melbourne, VIC"
  }'
```

### Delete emergency contact by ID:
```bash
curl -X DELETE http://localhost:8000/api/employees/emergency-contacts/1/
```

## Complete API Endpoints Summary

### Employee Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/employees/` | List all employees (with filtering) |
| POST | `/api/employees/` | Create new employee (generic) |
| **POST** | **`/api/employees/add_super_admin/`** | **Create Super Admin employee** |
| **POST** | **`/api/employees/add_sales_staff/`** | **Create Sales Staff employee** |
| GET | `/api/employees/{id}/` | Get employee details |
| PUT | `/api/employees/{id}/` | Update employee (full) |
| PATCH | `/api/employees/{id}/` | Update employee (partial) |
| DELETE | `/api/employees/{id}/` | Delete employee |
| GET | `/api/employees/stats/` | Get employee statistics |
| GET | `/api/employees/super_admins/` | List Super Admins only |
| GET | `/api/employees/sales_staff/` | List Sales Staff only |
| POST | `/api/employees/{id}/toggle_status/` | Toggle employee status |
| POST | `/api/employees/{id}/mark_resigned/` | Mark as resigned |

### Emergency Contact Management (Unified API)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/employees/{id}/emergency_contacts/` | Get emergency contacts for employee |
| POST | `/api/employees/{id}/add_emergency_contact/` | Add emergency contact to employee |
| PUT | `/api/employees/{id}/update_emergency_contact/` | Update emergency contact for employee |
| DELETE | `/api/employees/{id}/remove_emergency_contact/` | Remove emergency contact from employee |
| GET | `/api/employees/all_emergency_contacts/` | List all emergency contacts |
| GET | `/api/employees/emergency-contacts/{contact_id}/` | Get emergency contact by ID |
| PUT | `/api/employees/emergency-contacts/{contact_id}/` | Update emergency contact by ID |
| DELETE | `/api/employees/emergency-contacts/{contact_id}/` | Delete emergency contact by ID |

## Database Structure

The system maintains two separate database tables with a foreign key relationship:

### Employee Table
- Primary key: `id`
- Contains all employee information including Base64 profile images
- Account types: `super_admin`, `sales_staff`

### EmergencyContact Table
- Primary key: `id`
- Foreign key: `employee_id` (references Employee.id)
- Contains emergency contact information
- Relationship: One employee can have multiple emergency contacts (up to 5)

This design provides:
- **Data integrity** through foreign key constraints
- **Flexibility** for complex queries and reporting
- **Unified API** for simplified frontend integration
- **Scalability** for future enhancements
