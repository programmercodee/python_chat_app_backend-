"""
Email service supporting multiple providers:
1. Brevo (SMTP) - Works without domain verification, 300 free/day
2. Resend (API) - Requires verified domain
3. SMTP (Legacy) - For local development
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from app.config import settings

# Conditional import - resend may not be installed
try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        # Priority 1: Brevo (works without domain verification)
        if settings.brevo_api_key and settings.brevo_login and settings.brevo_sender_email:
            self.provider = "brevo"
            self.enabled = True
            logger.info("Email service initialized with Brevo SMTP")
        # Priority 2: Resend (requires verified domain)
        elif settings.resend_api_key and RESEND_AVAILABLE:
            resend.api_key = settings.resend_api_key
            self.provider = "resend"
            self.enabled = True
            logger.info("Email service initialized with Resend API")
        # Priority 3: Legacy SMTP (for local development)
        elif settings.mail_server and settings.mail_from:
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
        
        # Load Jinja2 templates
        template_dir = Path(__file__).parent.parent / 'templates' / 'email'
        if template_dir.exists():
            self.jinja_env = Environment(loader=FileSystemLoader(str(template_dir)))
        else:
            self.jinja_env = None

    async def send_otp_email(self, email: str, otp_code: str, template_name: str = "otp.html", subject: str = "TalkTogether - Password Reset OTP"):
        """Send OTP email with customizable template."""
        if not self.enabled:
            # Make OTP visible in terminal for testing
            print(f"\n{'='*50}")
            print(f"📧 MOCK OTP EMAIL (No email provider configured)")
            print(f"   To: {email}")
            print(f"   OTP Code: {otp_code}")
            print(f"{'='*50}\n")
            logger.info(f"Email service disabled. Mock OTP for {email}: {otp_code}")
            return

        if self.provider == "brevo":
            await self._send_via_brevo(email, otp_code, template_name, subject)
        elif self.provider == "resend":
            await self._send_via_resend(email, otp_code, template_name, subject)
        else:
            await self._send_via_smtp(email, otp_code, template_name, subject)
    
    async def send_registration_otp_email(self, email: str, otp_code: str):
        """Send OTP for registration email verification."""
        await self.send_otp_email(
            email, 
            otp_code, 
            template_name="registration_otp.html",
            subject="TalkTogether - Verify Your Email"
        )

    async def _send_via_brevo(self, email: str, otp_code: str, template_name: str, subject: str):
        """Send email using Brevo SMTP relay."""
        try:
            # Render HTML template
            if self.jinja_env:
                template = self.jinja_env.get_template(template_name)
                html_content = template.render(otp_code=otp_code)
            else:
                html_content = f"""
                <h2>Verification Code</h2>
                <p>Your code is: <strong>{otp_code}</strong></p>
                <p>This code expires in 10 minutes.</p>
                """
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{settings.brevo_sender_name} <{settings.brevo_sender_email}>"
            msg['To'] = email
            
            # Attach HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send via Brevo SMTP
            with smtplib.SMTP('smtp-relay.brevo.com', 587) as server:
                server.starttls()
                server.login(settings.brevo_login, settings.brevo_api_key)
                server.sendmail(settings.brevo_sender_email, email, msg.as_string())
            
            logger.info(f"OTP email sent to {email} via Brevo SMTP")
        except Exception as e:
            logger.error(f"Failed to send email via Brevo to {email}: {str(e)}")
            raise

    async def _send_via_resend(self, email: str, otp_code: str, template_name: str, subject: str):
        """Send email using Resend HTTP API."""
        try:
            # Render HTML template
            if self.jinja_env:
                template = self.jinja_env.get_template(template_name)
                html_content = template.render(otp_code=otp_code)
            else:
                html_content = f"""
                <h2>Verification Code</h2>
                <p>Your code is: <strong>{otp_code}</strong></p>
                <p>This code expires in 10 minutes.</p>
                """
            
            params = {
                "from": f"TalkTogether <{settings.resend_from_email}>",
                "to": [email],
                "subject": subject,
                "html": html_content
            }
            
            response = resend.Emails.send(params)
            logger.info(f"OTP email sent to {email} via Resend (id: {response.get('id', 'N/A')})")
        except Exception as e:
            logger.error(f"Failed to send email via Resend to {email}: {str(e)}")
            raise

    async def _send_via_smtp(self, email: str, otp_code: str, template_name: str, subject: str):
        """Send email using SMTP (fastapi-mail)."""
        try:
            from fastapi_mail import MessageSchema, MessageType
            message = MessageSchema(
                subject=subject,
                recipients=[email],
                template_body={"otp_code": otp_code},
                subtype=MessageType.html
            )
            
            await self.fastmail.send_message(message, template_name=template_name)
            logger.info(f"OTP email sent to {email} via SMTP")
        except Exception as e:
            logger.error(f"Failed to send email via SMTP to {email}: {str(e)}")
            raise


email_service = EmailService()
