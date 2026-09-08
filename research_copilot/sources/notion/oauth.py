"""Notion OAuth policy: URLs, trust rules, and callback path."""
from urllib.parse import urlsplit

NOTION_URL = 'https://mcp.notion.com/mcp'


def trusted_endpoint(url):
    parts = urlsplit(str(url))
    if parts.scheme != 'https' or not parts.hostname or not (
        parts.hostname == 'notion.com' or parts.hostname.endswith('.notion.com')
    ) or parts.username or parts.password:
        raise ValueError('Unexpected Notion authorization endpoint')
    return str(url)


class NotionAuthProvider:
    id = 'notion'
    display_name = 'Notion'
    server_url = NOTION_URL
    client_name = 'Research Copilot'
    callback_path = '/oauth/notion/callback'

    def trusted_endpoint(self, url):
        return trusted_endpoint(url)
