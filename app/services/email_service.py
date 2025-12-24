import logging
from pathlib import Path
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from app.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        # Only initialize if mail server is configured
        if settings.mail_server and settings.mail_from:
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
            self.enabled = True
        else:
            self.enabled = False
            logger.warning("SMTP settings not configured. Email sending is disabled.")

    async def send_otp_email(self, email: str, otp_code: str):
        if not self.enabled:
            # Make OTP visible in terminal for testing
            print(f"\n{'='*50}")
            print(f"📧 MOCK OTP EMAIL (SMTP not configured)")
            print(f"   To: {email}")
            print(f"   OTP Code: {otp_code}")
            print(f"{'='*50}\n")
            logger.info(f"Email service disabled. Mock OTP for {email}: {otp_code}")
            return

        try:
            message = MessageSchema(
                subject="TalkTogether - Password Reset OTP",
                recipients=[email],
                template_body={"otp_code": otp_code},
                subtype=MessageType.html
            )
            
            await self.fastmail.send_message(message, template_name="otp.html")
            logger.info(f"OTP email sent to {email}")
        except Exception as e:
            logger.error(f"Failed to send email to {email}: {str(e)}")
            raise

email_service = EmailService()
