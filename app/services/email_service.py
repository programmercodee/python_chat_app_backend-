"""
Email service using Resend API (works on all cloud providers).
Falls back to fastapi-mail SMTP for local development.
"""

import logging
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from app.config import settings

# Conditional import - resend may not be installed locally
try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        # Prefer Resend API if configured AND available (works on Render, Heroku, etc.)
        if settings.resend_api_key and RESEND_AVAILABLE:
            resend.api_key = settings.resend_api_key
            self.provider = "resend"
            self.enabled = True
            logger.info("Email service initialized with Resend API")
        elif settings.mail_server and settings.mail_from:
            # Fallback to SMTP (for local development)
            from fastapi_mail import FastMail, ConnectionConfig
            self.conf = ConnectionConfig(
                MAIL_USERNAME=settings.mail_username,
                MAIL_PASSWORD=settings.mail_password,
                MAIL_FROM=settings.mail_from,
                MAIL_PORT=settings.mail_port,
                MAIL_SERVER=settings.mail_server,
                MAIL_FROM_NAME=settings.mail_from_name,
                MAIL_STARTTLS=settings.mail_starttls,
                MAIL_SSL_TLS=settings.mail_ssl_tls,
                USE_CREDENTIALS=settings.use_credentials,
                VALIDATE_CERTS=settings.validate_certs,
                TEMPLATE_FOLDER=Path(__file__).parent.parent / 'templates' / 'email',
            )
            self.fastmail = FastMail(self.conf)
            self.provider = "smtp"
            self.enabled = True
            logger.info("Email service initialized with SMTP")
        else:
            self.enabled = False
            self.provider = None
            logger.warning("No email provider configured. Email sending is disabled.")
        
        # Load Jinja2 templates for Resend
        template_dir = Path(__file__).parent.parent / 'templates' / 'email'
        if template_dir.exists():
            self.jinja_env = Environment(loader=FileSystemLoader(str(template_dir)))
        else:
            self.jinja_env = None

    async def send_otp_email(self, email: str, otp_code: str):
        if not self.enabled:
            # Make OTP visible in terminal for testing
            print(f"\n{'='*50}")
            print(f"📧 MOCK OTP EMAIL (No email provider configured)")
            print(f"   To: {email}")
            print(f"   OTP Code: {otp_code}")
            print(f"{'='*50}\n")
            logger.info(f"Email service disabled. Mock OTP for {email}: {otp_code}")
            return

        if self.provider == "resend":
            await self._send_via_resend(email, otp_code)
        else:
            await self._send_via_smtp(email, otp_code)

    async def _send_via_resend(self, email: str, otp_code: str):
        """Send email using Resend HTTP API."""
        try:
            # Render HTML template
            if self.jinja_env:
                template = self.jinja_env.get_template("otp.html")
                html_content = template.render(otp_code=otp_code)
            else:
                # Fallback plain HTML
                html_content = f"""
                <h2>Password Reset OTP</h2>
                <p>Your OTP code is: <strong>{otp_code}</strong></p>
                <p>This code expires in 10 minutes.</p>
                """
            
            params = {
                "from": f"TalkTogether <{settings.resend_from_email}>",
                "to": [email],
                "subject": "TalkTogether - Password Reset OTP",
                "html": html_content
            }
            
            response = resend.Emails.send(params)
            logger.info(f"OTP email sent to {email} via Resend (id: {response.get('id', 'N/A')})")
        except Exception as e:
            logger.error(f"Failed to send email via Resend to {email}: {str(e)}")
            raise

    async def _send_via_smtp(self, email: str, otp_code: str):
        """Send email using SMTP (fastapi-mail)."""
        try:
            from fastapi_mail import MessageSchema, MessageType
            message = MessageSchema(
                subject="TalkTogether - Password Reset OTP",
                recipients=[email],
                template_body={"otp_code": otp_code},
                subtype=MessageType.html
            )
            
            await self.fastmail.send_message(message, template_name="otp.html")
            logger.info(f"OTP email sent to {email} via SMTP")
        except Exception as e:
            logger.error(f"Failed to send email via SMTP to {email}: {str(e)}")
            raise


email_service = EmailService()
