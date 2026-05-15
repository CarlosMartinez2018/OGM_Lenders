"""
Microsoft Graph API connector for Outlook email integration.
Supports reading emails from Exchange Online / Microsoft 365 mailboxes.

Setup instructions:
1. Go to https://portal.azure.com > App registrations > New registration
2. Set redirect URI: http://localhost (for testing)
3. API Permissions > Add:
   - Microsoft Graph > Application permissions:
     - Mail.Read (to read emails)
     - Mail.ReadBasic (minimal read)
   - Grant admin consent
4. Certificates & secrets > New client secret
5. Copy Tenant ID, Client ID, Client Secret to .env
"""
import logging
from datetime import datetime, timezone
import httpx
import msal
from app.core.config import settings
from app.models.schemas import EmailData

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


class OutlookConnector:
    def __init__(self):
        self.tenant_id = settings.azure_tenant_id
        self.client_id = settings.azure_client_id
        self.client_secret = settings.azure_client_secret
        self.mailbox = settings.outlook_mailbox
        self._access_token = None
        self._token_expiry = None

    @property
    def is_configured(self) -> bool:
        return all([self.tenant_id, self.client_id, self.client_secret, self.mailbox])

    async def _get_token(self) -> str:
        """Get or refresh Microsoft Graph API access token using MSAL."""
        if self._access_token and self._token_expiry and datetime.now(timezone.utc) < self._token_expiry:
            return self._access_token

        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret,
        )

        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

        if "access_token" not in result:
            error = result.get("error_description", result.get("error", "Unknown error"))
            raise ConnectionError(f"Failed to acquire token: {error}")

        self._access_token = result["access_token"]
        # Token typically expires in 1 hour; refresh 5 minutes early
        self._token_expiry = datetime.now(timezone.utc).replace(
            minute=datetime.now(timezone.utc).minute + 55
        )
        return self._access_token

    async def fetch_recent_emails(
        self, folder: str = "Inbox", count: int = 10
    ) -> list[EmailData]:
        """Fetch recent emails from Outlook mailbox."""
        if not self.is_configured:
            raise ValueError(
                "Outlook not configured. Set AZURE_TENANT_ID, AZURE_CLIENT_ID, "
                "AZURE_CLIENT_SECRET, and OUTLOOK_MAILBOX in .env"
            )

        token = await self._get_token()

        url = (
            f"{GRAPH_API_BASE}/users/{self.mailbox}/mailFolders/{folder}"
            f"/messages?$top={count}&$orderby=receivedDateTime desc"
            f"&$select=id,subject,from,receivedDateTime,body,hasAttachments"
        )

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                logger.error(f"Graph API error {response.status_code}: {response.text}")
                raise ConnectionError(f"Graph API error: {response.status_code} - {response.text[:200]}")

            data = response.json()
            emails = []

            for msg in data.get("value", []):
                sender_email = ""
                sender_data = msg.get("from", {}).get("emailAddress", {})
                sender_email = sender_data.get("address", "")

                body_content = msg.get("body", {}).get("content", "")
                body_type = msg.get("body", {}).get("contentType", "text")

                received = None
                if msg.get("receivedDateTime"):
                    try:
                        received = datetime.fromisoformat(
                            msg["receivedDateTime"].replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        received = datetime.now(timezone.utc)

                email = EmailData(
                    source="outlook",
                    message_id=msg.get("id", ""),
                    subject=msg.get("subject", "(no subject)"),
                    sender=sender_email,
                    sender_domain=sender_email.split("@")[1] if "@" in sender_email else "",
                    received_date=received,
                    body_text=body_content if body_type == "text" else "",
                    body_html=body_content if body_type == "html" else "",
                    has_attachments=msg.get("hasAttachments", False),
                )

                # If body is HTML and no plain text, use HTML as body_text
                if not email.body_text and email.body_html:
                    email.body_text = email.body_html

                emails.append(email)

            logger.info(f"Fetched {len(emails)} emails from {self.mailbox}/{folder}")
            return emails

    async def test_connection(self) -> dict:
        """Test the Graph API connection and return mailbox info."""
        if not self.is_configured:
            return {
                "status": "not_configured",
                "message": "Set Azure credentials in .env file",
            }

        try:
            token = await self._get_token()
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GRAPH_API_BASE}/users/{self.mailbox}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0,
                )

                if response.status_code == 200:
                    user = response.json()
                    return {
                        "status": "connected",
                        "mailbox": self.mailbox,
                        "display_name": user.get("displayName", ""),
                    }
                else:
                    return {
                        "status": "error",
                        "code": response.status_code,
                        "message": response.text[:200],
                    }
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Singleton
outlook = OutlookConnector()
