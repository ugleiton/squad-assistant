from ...application.ports import ChatProvider
from ...domain.enums import ChatProviderType
from ..persistence.models import ChatConnection
from ..security import decrypt
from .mattermost import MattermostProvider
from .slack import SlackProvider
from .webhook import IncomingWebhookProvider


def provider_for_connection(conn: ChatConnection) -> ChatProvider:
    token = decrypt(conn.bot_token) or ""
    if conn.provider == ChatProviderType.slack:
        return SlackProvider(token, conn.bot_user_id)
    if conn.provider == ChatProviderType.mattermost:
        if not conn.base_url:
            raise ValueError("Mattermost connection needs base_url")
        return MattermostProvider(conn.base_url, token, conn.bot_user_id)
    raise ValueError(f"Unknown provider {conn.provider}")


def webhook_provider(url: str, provider: str = "slack") -> ChatProvider:
    return IncomingWebhookProvider(url, provider)
