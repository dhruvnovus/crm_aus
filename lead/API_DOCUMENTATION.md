# Lead Management API Documentation

## Overview

The Lead Management API provides comprehensive functionality for managing leads in the CRM system. This API supports all CRUD operations, filtering, searching, bulk operations, and lead status management.

## Base URL

```
http://localhost:8000/api/leads/
```

## Authentication

Currently, the API does not require authentication. In production, implement proper authentication mechanisms.

## Lead Model Fields

### Personal Information
- `title` (string): Mr, Mrs, Miss, Ms, Other
- `first_name` (string, required): Lead's first name
- `last_name` (string, required): Lead's last name
- `company_name` (string, required): Company name

### Contact Information
- `contact_number` (string, required): Phone number
- `email_address` (email, required): Primary email address
- `custom_email_addresses` (text, optional): Additional emails (comma-separated)
- `address` (text, optional): Full address

### Lead Details
- `event` (string, optional): Associated event
- `lead_type` (string): exhibitor, sponsor, visitor
- `booth_size` (string, optional): Booth size preference
- `sponsorship_type` (string, optional): Type of sponsorship
- `registration_groups` (string, optional): Registration groups

### Lead Management
- `status` (string): new, info_pack, attempted_contact, contacted, contract_invoice_sent, contract_signed_paid, withdrawn, lost, converted, future
- `intensity` (string): cold, warm, hot, sql
- `opportunity_price` (decimal, optional): Opportunity value
- `tags` (string, optional): Tags (comma-separated)
- `assigned_sales_staff` (string, optional): Assigned sales staff member

### Lead Source
- `how_did_you_hear` (string, optional): How they heard about us
- `reason_for_enquiry` (text, optional): Reason for enquiry

### Timestamps
- `date_received` (datetime, auto): Date when lead was received
- `created_at` (datetime, auto): Creation timestamp
- `updated_at` (datetime, auto): Last update timestamp

## API Endpoints

### 1. List Leads
**GET** `/api/leads/`

Returns a paginated list of all leads with optional filtering.

**Query Parameters:**
- `page` (int): Page number for pagination
- `page_size` (int): Number of items per page (max 500)
- `status` (string): Filter by lead status
- `lead_type` (string): Filter by lead type
- `intensity` (string): Filter by lead intensity
- `assigned_sales_staff` (string): Filter by assigned sales staff
- `event` (string): Filter by event
- `status_category` (string): Filter by status category (active, inactive)
- `search` (string): Search in name, company, email, phone, tags
- `ordering` (string): Order by field (prefix with - for descending)

**Response:** Returns paginated list of leads (HTTP 200).

**Example:**
```bash
curl "http://localhost:8000/api/leads/?status=new&page=1&page_size=50"
```

### 2. Create Lead
**POST** `/api/leads/`

Creates a new lead.

**Request Body:**
```json
{
    "title": "mr",
    "first_name": "John",
    "last_name": "Doe",
    "company_name": "Example Company",
    "contact_number": "+61412345678",
    "email_address": "john.doe@example.com",
    "custom_email_addresses": "john@example.com, j.doe@example.com",
    "address": "123 Main St, Sydney, NSW 2000",
    "event": "Aged & Disability Expo Newcastle",
    "lead_type": "exhibitor",
    "booth_size": "3x3",
    "sponsorship_type": "Gold",
    "registration_groups": "Group A",
    "status": "new",
    "intensity": "cold",
    "opportunity_price": "1500.00",
    "tags": "Newcastle, Exhibitor, New",
    "how_did_you_hear": "Website",
    "reason_for_enquiry": "Interested in exhibiting at the expo",
    "assigned_sales_staff": "Sales Team A"
}
```

**Response:** Returns the created lead with full details (HTTP 201).

### 3. Retrieve Lead
**GET** `/api/leads/{id}/`

Returns detailed information about a specific lead.

**Response:** Returns lead details (HTTP 200).

**Example:**
```bash
curl "http://localhost:8000/api/leads/1/"
```

### 4. Update Lead (Full)
**PUT** `/api/leads/{id}/`

Updates all fields of a lead.

**Request Body:** Same as create lead.

**Response:** Returns updated lead details (HTTP 200).

### 5. Update Lead (Partial)
**PATCH** `/api/leads/{id}/`

Updates specific fields of a lead.

**Request Body:**
```json
{
    "status": "contacted",
    "intensity": "warm",
    "opportunity_price": "2000.00"
}
```

**Response:** Returns updated lead details (HTTP 200).

### 6. Delete Lead
**DELETE** `/api/leads/{id}/`

Deletes a lead from the system.

**Response:** No content (HTTP 204).

### 7. Get Lead Statistics
**GET** `/api/leads/stats/`

Returns comprehensive statistics about leads.

**Response:**
```json
{
    "total_leads": 1500,
    "new_leads": 133,
    "info_pack_leads": 34,
    "attempted_contact_leads": 9,
    "contacted_leads": 18,
    "contract_invoice_sent_leads": 54,
    "contract_signed_paid_leads": 225,
    "withdrawn_leads": 12,
    "lost_leads": 3684,
    "converted_leads": 251,
    "future_leads": 1009,
    "total_opportunity_value": "144972.00",
    "exhibitor_count": 1200,
    "sponsor_count": 200,
    "visitor_count": 100
}
```

### 8. Get Leads by Status
**GET** `/api/leads/by_status/?status={status}`

Returns leads filtered by specific status.

**Query Parameters:**
- `status` (string, required): Lead status to filter by

**Response:** Returns paginated list of leads with specified status (HTTP 200).

### 9. Get New Leads
**GET** `/api/leads/new_leads/`

Returns all new leads.

**Response:** Returns paginated list of new leads (HTTP 200).

### 10. Get Lost Leads
**GET** `/api/leads/lost_leads/`

Returns all lost leads.

**Response:** Returns paginated list of lost leads (HTTP 200).

### 11. Get Converted Leads
**GET** `/api/leads/converted_leads/`

Returns all converted leads.

**Response:** Returns paginated list of converted leads (HTTP 200).

### 12. Get Future Leads
**GET** `/api/leads/future_leads/`

Returns all future leads.

**Response:** Returns paginated list of future leads (HTTP 200).

### 13. Update Lead Status
**POST** `/api/leads/{id}/update_status/`

Updates the status of a specific lead.

**Request Body:**
```json
{
    "status": "contacted"
}
```

**Response:** Returns updated lead details (HTTP 200).

### 14. Assign Lead to Sales Staff
**POST** `/api/leads/{id}/assign_sales_staff/`

Assigns a lead to a specific sales staff member.

**Request Body:**
```json
{
    "assigned_sales_staff": "John Smith"
}
```

**Response:** Returns updated lead details (HTTP 200).

### 15. Bulk Import Leads
**POST** `/api/leads/bulk_import/`

Imports multiple leads at once.

**Request Body:**
```json
{
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
```

**Response:**
```json
{
    "created_count": 2,
    "error_count": 0,
    "created_leads": [...],
    "errors": []
}
```

### 16. Export Leads
**GET** `/api/leads/export/`

Exports leads to CSV format.

**Query Parameters:** Same filtering options as list leads.

**Response:** CSV file download.

## Lead Status Workflow

The lead status follows this typical workflow:

1. **New** → Lead is first created
2. **Info Pack** → Information pack sent to lead
3. **Attempted Contact** → Sales team attempted to contact
4. **Contacted** → Successfully contacted the lead
5. **Contract & Invoice Sent** → Contract and invoice sent
6. **Contract Signed & Paid** → Contract signed and payment received
7. **Converted** → Lead successfully converted
8. **Lost** → Lead lost to competition or not interested
9. **Withdrawn** → Lead withdrew from process
10. **Future** → Lead for future events

## Lead Types

- **Exhibitor**: Companies wanting to exhibit at events
- **Sponsor**: Companies wanting to sponsor events
- **Visitor**: Individuals wanting to visit events

## Lead Intensity Levels

- **Cold**: New lead with no prior contact
- **Warm**: Lead showing some interest
- **Hot**: Lead with high interest and potential
- **SQL**: Sales Qualified Lead - ready for sales process

## Filtering and Search

### Filter Options
- Filter by status, lead type, intensity, assigned sales staff, event
- Filter by status category (active/inactive)
- Search across name, company, email, phone, tags

### Sorting Options
- Sort by date_received, created_at, updated_at, first_name, last_name, company_name, opportunity_price
- Use `-` prefix for descending order

### Pagination
- Default page size: 100 leads
- Maximum page size: 500 leads
- Use `page` and `page_size` parameters

## Error Handling

The API returns appropriate HTTP status codes:

- **200**: Success
- **201**: Created
- **204**: No Content (for deletions)
- **400**: Bad Request (validation errors)
- **404**: Not Found
- **500**: Internal Server Error

Error responses include detailed error messages:

```json
{
    "error": "Status is required.",
    "field_errors": {
        "email_address": ["A lead with this email already exists."]
    }
}
```

## Example Usage

### Create a New Lead
```bash
curl -X POST http://localhost:8000/api/leads/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "mr",
    "first_name": "Anthony",
    "last_name": "Duggan",
    "company_name": "Teqstar Ramps",
    "contact_number": "+61412345678",
    "email_address": "anthony@teqstar.com",
    "lead_type": "exhibitor",
    "status": "new",
    "event": "Aged & Disability Expo Newcastle",
    "tags": "Newcastle, Exhibitor"
  }'
```

### Get All New Leads
```bash
curl "http://localhost:8000/api/leads/new_leads/"
```

### Update Lead Status
```bash
curl -X POST http://localhost:8000/api/leads/1/update_status/ \
  -H "Content-Type: application/json" \
  -d '{"status": "contacted"}'
```

### Search Leads
```bash
curl "http://localhost:8000/api/leads/?search=Anthony&status=new"
```

### Export Leads to CSV
```bash
curl "http://localhost:8000/api/leads/export/?status=new" -o leads_export.csv
```

## Complete API Endpoints Summary

### Lead Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/leads/` | List all leads (with filtering) |
| POST | `/api/leads/` | Create new lead |
| GET | `/api/leads/{id}/` | Get lead details |
| PUT | `/api/leads/{id}/` | Update lead (full) |
| PATCH | `/api/leads/{id}/` | Update lead (partial) |
| DELETE | `/api/leads/{id}/` | Delete lead |
| GET | `/api/leads/stats/` | Get lead statistics |
| GET | `/api/leads/by_status/` | Get leads by status |
| GET | `/api/leads/new_leads/` | Get new leads |
| GET | `/api/leads/lost_leads/` | Get lost leads |
| GET | `/api/leads/converted_leads/` | Get converted leads |
| GET | `/api/leads/future_leads/` | Get future leads |
| POST | `/api/leads/{id}/update_status/` | Update lead status |
| POST | `/api/leads/{id}/assign_sales_staff/` | Assign to sales staff |
| POST | `/api/leads/bulk_import/` | Bulk import leads |
| GET | `/api/leads/export/` | Export leads to CSV |

## Integration with Swagger UI

All endpoints are documented in Swagger UI at:
- **Swagger UI**: `http://localhost:8000/api/docs/`
- **ReDoc**: `http://localhost:8000/api/redoc/`

The Swagger UI provides:
- Interactive API testing
- Request/response examples
- Schema validation
- Try it out functionality
- Comprehensive documentation

## Database Schema

The Lead model creates a `leads` table with the following structure:

```sql
CREATE TABLE leads (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(10) NOT NULL DEFAULT 'mr',
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    company_name VARCHAR(200) NOT NULL,
    contact_number VARCHAR(20) NOT NULL,
    email_address VARCHAR(254) NOT NULL,
    custom_email_addresses TEXT,
    address TEXT,
    event VARCHAR(200),
    lead_type VARCHAR(20) NOT NULL DEFAULT 'exhibitor',
    booth_size VARCHAR(100),
    sponsorship_type VARCHAR(100),
    registration_groups VARCHAR(200),
    status VARCHAR(30) NOT NULL DEFAULT 'new',
    intensity VARCHAR(20) NOT NULL DEFAULT 'cold',
    opportunity_price DECIMAL(10,2),
    tags VARCHAR(500),
    how_did_you_hear VARCHAR(200),
    reason_for_enquiry TEXT,
    assigned_sales_staff VARCHAR(200),
    date_received DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
```

## Performance Considerations

- Pagination is implemented for all list endpoints
- Database indexes are recommended on frequently queried fields
- Bulk operations are available for importing large datasets
- Export functionality supports filtering for targeted exports
- Search is optimized for common lead fields

This comprehensive Lead Management API provides all the functionality needed for a modern CRM system with lead tracking, status management, and sales pipeline optimization.
