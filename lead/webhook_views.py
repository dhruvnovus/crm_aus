from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes
from .models import Lead, RegistrationGroup, LeadTag, SponsorshipType


@extend_schema(
    summary="Zapier lead webhook",
    description="Create or update a Lead from Zapier payload.",
    tags=["Leads"],
    request=OpenApiTypes.OBJECT,
    responses={200: OpenApiTypes.OBJECT},
)
@api_view(['POST'])
@permission_classes([AllowAny])
def zapier_lead_webhook(request):
    """
    Webhook endpoint for Zapier to create/update Leads.

    Expected Zapier fields (column names):
    - Account Id
    - Zap Id
    - Lead Reference
    - Lead Name
    - Lead Email
    - Phone Number
    - Company Name
    - Participation Type
    - Source
    - Special Notes
    - Zap Path Run Id
    - Parent Task History Link

    Mapping to Lead model:
    - Lead Name          -> lead_name (also split into first_name / last_name)
    - Lead Email         -> email_address
    - Phone Number       -> contact_number
    - Company Name       -> company_name
    - Participation Type -> lead_type
    - Source             -> how_did_you_hear
    - Special Notes      -> reason_for_enquiry

    Other Zapier fields (Account Id, Zap Id, Lead Reference, Zap Path Run Id,
    Parent Task History Link) are currently ignored and not stored.
    """
    data = request.data
    print(data, "data from zapier")

    # Normalise keys (case-insensitive, ignore spaces/underscores) so that
    # Zapier field name variations still map correctly.
    normalized = {}
    for key, value in data.items():
        normalized[key] = value
        norm_key = str(key).strip().lower().replace(" ", "").replace("_", "")
        if norm_key not in normalized:
            normalized[norm_key] = value

    def _get_any(*candidates):
        """
        Helper to fetch a value from request data by trying multiple key variants,
        including a normalised (lowercase, no space/underscore) version.
        """
        for candidate in candidates:
            # direct key match
            if candidate in data and data.get(candidate) not in ("", None):
                return data.get(candidate)
            # normalised key match
            norm = str(candidate).strip().lower().replace(" ", "").replace("_", "")
            if norm in normalized and normalized.get(norm) not in ("", None):
                return normalized.get(norm)
        return ""

    # Support multiple naming styles from Zapier
    raw_lead_name = _get_any("Lead Name", "lead_name", "leadname", "name")
    title = _get_any("Title", "title", "title", "title")
    lead_email = _get_any("Lead Email", "lead_email", "email", "email_address")
    phone_number = _get_any("Phone Number", "phone_number", "phone", "contact_number")
    company_name = _get_any("Company Name", "company_name")
    participation_type = _get_any("Participation Type", "participation_type", "lead_type")
    source = _get_any("Source", "source", "how_did_you_hear")
    special_notes = _get_any("Special Notes", "special_notes", "notes", "reason_for_enquiry")
    first_name = _get_any("First Name", "first_name", "firstname", "fname")
    last_name = _get_any("Last Name", "last_name", "lastname", "lname")
    full_name = _get_any("Full Name", "full_name", "fullname", "full name")
    lead_stage = _get_any("Lead Stage", "lead_stage", "leadstage", "lead stage")
    lead_pipeline = _get_any("Lead Pipeline", "lead_pipeline", "leadpipeline", "lead pipeline")
    booth_size = _get_any("Booth Size", "booth_size", "boothsize", "booth size")
    sponsorship_type = _get_any("Sponsorship Type", "sponsorship_type", "sponsorshiptype", "sponsorship type")
    registration_group = _get_any("Registration Group", "registration_group", "registrationgroup", "registration group")
    lead_status = _get_any("Status", "status", "status", "status")
    intensity = _get_any("Intensity", "intensity", "intensity", "intensity")
    opportunity_price = _get_any("Opportunity Price", "opportunity_price", "opportunityprice", "opportunity price")
    tags = _get_any("Tags", "tags", "tags", "tags")
    # If no explicit full_name, fall back to "Lead Name"
    if not full_name:
        full_name = raw_lead_name or ""

    # Split full name into first and last name (very simple split)
    name_parts = full_name.strip().split()
    if not first_name and not last_name:
        # Only derive if explicit first/last not provided
        if len(name_parts) == 0:
            first_name = "Unknown"
            last_name = ""
        elif len(name_parts) == 1:
            first_name = name_parts[0]
            last_name = ""
        else:
            first_name = name_parts[0]
            last_name = " ".join(name_parts[1:])

    # Normalize title, status, and intensity to valid choices
    # Title field has default='mr' in model, so use that if not provided
    normalized_title = 'mr'  # Default to model's default
    if title:
        title_lower = str(title).strip().lower()
        valid_titles = [choice[0].lower() for choice in Lead.TITLE_CHOICES]
        if title_lower in valid_titles:
            normalized_title = title_lower
        # If invalid, keep default 'mr'
    
    normalized_status = 'new'  # Default status
    if lead_status:
        status_lower = str(lead_status).strip().lower()
        valid_statuses = [choice[0].lower() for choice in Lead.STATUS_CHOICES]
        if status_lower in valid_statuses:
            normalized_status = status_lower
    
    normalized_intensity = 'cold'  # Default intensity
    if intensity:
        intensity_lower = str(intensity).strip().lower()
        valid_intensities = [choice[0].lower() for choice in Lead.INTENSITY_CHOICES]
        if intensity_lower in valid_intensities:
            normalized_intensity = intensity_lower

    # Normalize lead_type
    normalized_lead_type = Lead.TYPE_CHOICES[0][0]  # Default
    if participation_type:
        participation_lower = str(participation_type).strip().lower()
        valid_types = [choice[0].lower() for choice in Lead.TYPE_CHOICES]
        if participation_lower in valid_types:
            normalized_lead_type = participation_lower

    # Convert opportunity_price to Decimal if it's a string
    normalized_opportunity_price = None
    if opportunity_price:
        try:
            from decimal import Decimal
            if isinstance(opportunity_price, str):
                normalized_opportunity_price = Decimal(str(opportunity_price).strip())
            else:
                normalized_opportunity_price = Decimal(str(opportunity_price))
        except (ValueError, TypeError):
            # If conversion fails, leave as None
            normalized_opportunity_price = None

    # Ensure required fields have defaults
    # first_name is already set to "Unknown" if empty (line 1633)
    # Ensure company_name, contact_number, and email_address are not None (can be empty strings)
    normalized_company_name = company_name or ""
    normalized_contact_number = phone_number or ""
    normalized_email = lead_email or ""

    # Build defaults for Lead model (excluding M2M fields)
    defaults = {
        "title": normalized_title,
        "first_name": first_name or "Unknown",
        "last_name": last_name or "",
        "company_name": normalized_company_name,
        "contact_number": normalized_contact_number,
        "email_address": normalized_email,
        "lead_name": raw_lead_name or None,
        "lead_type": normalized_lead_type,
        "how_did_you_hear": source or None,
        "reason_for_enquiry": special_notes or None,
        "lead_stage": lead_stage or None,
        "lead_pipeline": lead_pipeline or None,
        "booth_size": booth_size or None,
        "status": normalized_status,
        "intensity": normalized_intensity,
        "opportunity_price": normalized_opportunity_price,
    }

    # Debug logging to verify what we are about to save
    print("Zapier defaults:", defaults)

    # Create Lead without M2M fields
    lead = Lead.objects.create(**defaults)

    # Handle ManyToMany relationships after Lead creation
    # Sponsorship Type (comma-separated)
    if sponsorship_type:
        sponsorship_type_names = [s.strip() for s in str(sponsorship_type).split(',') if s.strip()]
        sponsorship_type_objects = []
        for name in sponsorship_type_names:
            sponsorship_type_obj, created = SponsorshipType.objects.get_or_create(
                name=name,
                defaults={'is_deleted': False}
            )
            sponsorship_type_objects.append(sponsorship_type_obj)
        if sponsorship_type_objects:
            lead.sponsorship_type.set(sponsorship_type_objects)

    # Registration Groups (comma-separated)
    if registration_group:
        registration_group_names = [r.strip() for r in str(registration_group).split(',') if r.strip()]
        registration_group_objects = []
        for name in registration_group_names:
            registration_group_obj, created = RegistrationGroup.objects.get_or_create(
                name=name,
                defaults={'is_deleted': False}
            )
            registration_group_objects.append(registration_group_obj)
        if registration_group_objects:
            lead.registration_groups.set(registration_group_objects)

    # Tags (comma-separated)
    if tags:
        tag_names = [t.strip() for t in str(tags).split(',') if t.strip()]
        tag_objects = []
        for name in tag_names:
            tag_obj, created = LeadTag.objects.get_or_create(
                name=name,
                defaults={'is_deleted': False}
            )
            tag_objects.append(tag_obj)
        if tag_objects:
            lead.tags.set(tag_objects)

    created = True

    return Response(
        {"status": "success", "created": created, "lead_id": lead.id},
        status=status.HTTP_200_OK,
    )

