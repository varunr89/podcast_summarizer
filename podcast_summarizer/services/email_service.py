import os
from typing import Dict, List, Any
from azure.communication.email import EmailClient
from ..api.common import logger
import markdown

class EmailService:
    def __init__(self):
        """Initialize the Azure Communication Service email client."""
        logger.info("Initializing Azure Communication Service email client")
        self.connection_string = os.getenv("AZURECONNECTIONSTRING")
        self.sender_email = os.getenv("SENDER_EMAIL")
        
        if not all([self.connection_string, self.sender_email]):
            logger.error("Azure Communication Service credentials not configured")
            raise ValueError("Azure Communication Service credentials not configured")
        
        try:
            logger.debug("Creating Azure Communication Service client")
            self.client = EmailClient.from_connection_string(self.connection_string)
            logger.info("Azure Communication Service client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Azure Communication Service client: {str(e)}")
            raise
    
    def send(self, to_email: str, subject: str, content: str) -> bool:
        """
        Send an email using Azure Communication Service.
        
        Args:
            to_email: Recipient's email address
            subject: Email subject
            content: Email content (supports markdown formatting)
            
        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        try:
            logger.info(f"Preparing to send email to: {to_email}")
            logger.debug(f"Email subject: {subject}")
            
            # Format the content as HTML
            logger.debug("Converting markdown content to HTML")
            html_content = self._markdown_to_html(content)
            
            message = {
                "senderAddress": self.sender_email,
                "recipients": {
                    "to": [{"address": to_email}],
                },
                "content": {
                    "subject": subject,
                    "html": f"""
                    <html>
                        <body style="font-family: Arial, sans-serif; max-width: 800px; margin: auto; padding: 20px;">
                            {html_content}
                        </body>
                    </html>
                    """
                }
            }
            
            logger.debug("Initiating email send request")
            # Send email using Azure Communication Service
            poller = self.client.begin_send(message)
            logger.info("Email send request initiated, waiting for completion")
            result = poller.result()
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    def _markdown_to_html(self, markdown_text: str) -> str:
        logger.debug("Converting markdown to HTML using markdown module")
        body_html = markdown.markdown(markdown_text, extensions=["extra", "sane_lists"])

        styled_html = f"""
        <html>
            <head>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        color: #333;
                        max-width: 700px;
                        margin: auto;
                        padding: 20px;
                    }}
                    h1, h2, h3 {{
                        color: #1a1a1a;
                    }}
                    ul {{
                        margin-left: 20px;
                        padding-left: 10px;
                        color: #444;
                    }}
                    li {{
                        margin-bottom: 8px;
                    }}
                    hr {{
                        border: none;
                        border-top: 1px solid #ddd;
                        margin: 30px 0;
                    }}
                </style>
            </head>
            <body>
                {body_html}
            </body>
        </html>
        """
        return styled_html