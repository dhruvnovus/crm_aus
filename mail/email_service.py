"""
Email service for sending emails via SMTP2GO API
"""
import requests
import json
import logging
import base64
from django.conf import settings

logger = logging.getLogger(__name__)


def send_email_via_smtp2go(
    to_emails,
    subject,
    text_body,
    sender_email=None,
    cc_emails=None,
    bcc_emails=None,
    html_body=None,
    attachments=None
):
    """
    Send email using SMTP2GO API.
    
    Args:
        to_emails: List of recipient email addresses or single email string
        subject: Email subject
        text_body: Plain text email body
        sender_email: Sender email address (defaults to DEFAULT_FROM_EMAIL from settings)
        cc_emails: List of CC email addresses (optional)
        bcc_emails: List of BCC email addresses (optional)
        html_body: HTML email body (optional)
        attachments: List of attachment dictionaries with 'filename', 'content', and 'content_type' (optional)
    
    Returns:
        dict: Response from SMTP2GO API with 'success' and 'data' keys
    """
    # Get API key and sender email from settings
    api_key = getattr(settings, 'SMTP2GO_API_KEY', None)
    if not api_key:
        logger.error("SMTP2GO_API_KEY is not configured in settings")
        return {
            'success': False,
            'error': 'SMTP2GO_API_KEY is not configured'
        }
    
    # Use DEFAULT_FROM_EMAIL if sender_email not provided
    if not sender_email:
        sender_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        if not sender_email:
            logger.error("DEFAULT_FROM_EMAIL is not configured in settings")
            return {
                'success': False,
                'error': 'DEFAULT_FROM_EMAIL is not configured'
            }
    
    # Ensure to_emails is a list
    if isinstance(to_emails, str):
        to_emails = [to_emails]
    
    # Prepare payload
    payload = {
        "api_key": api_key,
        "to": to_emails,
        "sender": sender_email,
        "subject": subject,
        "text_body": text_body,
    }
    
    # Add HTML body if provided
    if html_body:
        payload["html_body"] = html_body
    
    # Add CC recipients if provided
    if cc_emails:
        if isinstance(cc_emails, str):
            cc_emails = [cc_emails]
        payload["cc"] = cc_emails
    
    # Add BCC recipients if provided
    if bcc_emails:
        if isinstance(bcc_emails, str):
            bcc_emails = [bcc_emails]
        payload["bcc"] = bcc_emails
    
    # Add attachments if provided
    if attachments:
        attachment_list = []
        for attachment in attachments:
            if isinstance(attachment, dict) and 'filename' in attachment and 'content' in attachment:
                # Encode attachment content to base64
                if isinstance(attachment['content'], bytes):
                    content_base64 = base64.b64encode(attachment['content']).decode('utf-8')
                else:
                    # If content is already a string, assume it's base64
                    content_base64 = attachment['content']
                content_type = attachment.get('content_type') or 'application/octet-stream'
                
                # SMTP2GO expects attachment keys: name, type, data
                filename = attachment['filename'] or 'attachment'
                attachment_dict = {
                    # Official SMTP2GO fields
                    "filename": filename,
                    "mimetype": content_type,
                    "fileblob": content_base64,
                    # Additional aliases for compatibility
                    "name": filename,
                    "type": content_type,
                    "data": content_base64,
                    "filetype": content_type,
                    "filecontent": content_base64,
                }
                attachment_list.append(attachment_dict)
        
        if attachment_list:
            payload["attachments"] = attachment_list
    
    # SMTP2GO API endpoint
    url = "https://api.smtp2go.com/v3/email/send"
    
    try:
        logger.info(f"Sending email via SMTP2GO: to={to_emails}, subject={subject}")
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        
        # Check if the API returned success
        if result.get('data', {}).get('error'):
            error_msg = result['data']['error']
            logger.error(f"SMTP2GO API error: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'response': result
            }
        
        logger.info(f"Email sent successfully via SMTP2GO: to={to_emails}, subject={subject}")
        return {
            'success': True,
            'data': result.get('data', {}),
            'response': result
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send email via SMTP2GO: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': f'Request failed: {str(e)}'
        }
    except Exception as e:
        logger.error(f"Unexpected error sending email via SMTP2GO: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        }

