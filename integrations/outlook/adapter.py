"""Microsoft Graph v1.0 adapter. Read + unsent drafts only; send routes are disabled."""
import asyncio
import re
from dataclasses import dataclass
from urllib.parse import quote, urlsplit

import httpx
from pydantic import ValidationError

from integrations.outlook.models import Attachment, GraphPage, MailboxProfile, MailFolder, MailboxSettings, Message

ORIGIN = "https://graph.microsoft.com"
SELECT = "id,conversationId,internetMessageId,changeKey,subject,from,sender,toRecipients,ccRecipients,receivedDateTime,lastModifiedDateTime,body,hasAttachments,isDraft"


@dataclass
class GraphError(Exception):
    code: str
    status: int | None = None
    uncertain: bool = False
    retry_after: int | None = None

    def __str__(self):
        return "Microsoft Graph operation failed: " + self.code


class MicrosoftGraphMailAdapter:
    def __init__(self, config, token_provider, audit, fixture_transport=None):
        if fixture_transport is not None and not isinstance(fixture_transport, httpx.MockTransport):
            raise TypeError("Only MockTransport fixture injection is permitted")
        self.config, self.token_provider, self.audit = config, token_provider, audit
        self.fixture = fixture_transport is not None
        self.mailbox_verified = False
        self.client = httpx.AsyncClient(base_url=ORIGIN, transport=fixture_transport,
            timeout=20, trust_env=False, follow_redirects=False,
            headers={"Accept": "application/json", "Content-Type": "application/json",
                     "Prefer": 'IdType="ImmutableId", outlook.body-content-type="text", odata.maxpagesize=25'})

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()

    @staticmethod
    def identifier(value):
        if not isinstance(value, str) or not value or len(value) > 2048 or any(ord(c) < 32 for c in value):
            raise ValueError("Invalid Graph resource identifier")
        return quote(value, safe="")

    @staticmethod
    def cursor(url, expected_path):
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.netloc != "graph.microsoft.com"
                or parsed.path != expected_path or parsed.fragment or parsed.username or parsed.password):
            raise PermissionError("Graph cursor origin/resource mismatch")
        return url

    async def _request(self, method, path, operation, *, params=None, body=None, binary=False, draft=False):
        if not self.fixture and not self.config.network_authorized:
            raise PermissionError("Microsoft owner authentication boundary")
        if operation != "profile" and not self.mailbox_verified:
            raise PermissionError("Verify exact mailbox profile before mail access")
        allowed_draft = method == "POST" and draft and (
            path == "/v1.0/me/messages" or re.fullmatch(r"/v1.0/me/messages/[^/]+/create(Reply|Forward)", path))
        if method != "GET" and not allowed_draft:
            raise PermissionError("Production send/reply/forward and other Graph writes are disabled")
        if allowed_draft and not self.fixture and not self.config.drafts_authorized:
            raise PermissionError("Owner draft-creation authorization required")
        parsed = urlsplit(path)
        if ((parsed.scheme or parsed.netloc) and
                (parsed.scheme != "https" or parsed.netloc != "graph.microsoft.com")):
            raise PermissionError("Graph origin mismatch")
        if not (parsed.path == "/v1.0/me" or parsed.path.startswith("/v1.0/me/")):
            raise PermissionError("Graph resource boundary mismatch")
        token = await asyncio.to_thread(self.token_provider)
        facts = {"operation": operation, "fixture": self.fixture, "credential_class": "microsoft_delegated"}
        self.audit({**facts, "event": "GRAPH_REQUEST_STARTED"})
        try:
            async with self.client.stream(method, path, params=params, json=body,
                    headers={"Authorization": "Bearer " + token.get_secret_value()}) as response:
                status = response.status_code
                if not 200 <= status < 300:
                    code = {401: "authentication_required", 403: "permission_denied", 404: "not_found",
                            410: "delta_reset_required", 429: "rate_limited"}.get(status, "http_error")
                    retry = response.headers.get("retry-after", "")
                    raise GraphError(code, status, method != "GET" and status >= 500,
                                     min(int(retry), 3600) if retry.isdigit() else None)
                raw = bytearray()
                limit = 10_000_000 if binary else 2_000_000
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > limit:
                        raise GraphError("response_too_large", status, method != "GET")
                if binary:
                    result = bytes(raw)
                else:
                    import json
                    try:
                        result = json.loads(raw)
                        if not isinstance(result, dict) or "error" in result:
                            raise ValueError()
                    except (ValueError, TypeError):
                        raise GraphError("invalid_response", status, method != "GET") from None
                self.audit({**facts, "event": "GRAPH_REQUEST_SUCCEEDED", "status": status})
                return result
        except httpx.HTTPError:
            self.audit({**facts, "event": "GRAPH_REQUEST_FAILED", "error_code": "transport_error"})
            raise GraphError("transport_error", uncertain=method != "GET") from None
        except GraphError as error:
            self.audit({**facts, "event": "GRAPH_REQUEST_FAILED", "error_code": error.code, "status": error.status})
            raise

    async def get_mailbox_profile(self):
        profile = MailboxProfile.model_validate(await self._request("GET", "/v1.0/me", "profile",
                                              params={"$select": "id,mail,userPrincipalName,displayName"}))
        if (profile.mail or "").casefold() != self.config.mailbox.casefold():
            raise PermissionError("Graph mailbox identity does not match the dedicated mailbox")
        self.mailbox_verified = True
        return profile

    async def list_mail_folders(self):
        page = GraphPage.model_validate(await self._request("GET", "/v1.0/me/mailFolders", "folders",
                                                            params={"$top": 50}))
        return [MailFolder.model_validate(row) for row in page.value], page.next_link

    async def get_mailbox_settings(self):
        raw = await self._request("GET", "/v1.0/me/mailboxSettings", "mailbox_settings",
                                  params={"$select": "timeZone,language,dateFormat,timeFormat"})
        try:
            return MailboxSettings.model_validate(raw)
        except ValidationError:
            raise GraphError("invalid_mailbox_settings") from None

    async def get_message(self, message_id):
        raw = await self._request("GET", "/v1.0/me/messages/" + self.identifier(message_id), "message",
                                  params={"$select": SELECT})
        result = Message.model_validate(raw)
        if result.id != message_id:
            raise GraphError("message_identity_mismatch")
        return result

    async def _messages(self, params):
        page = GraphPage.model_validate(await self._request("GET", "/v1.0/me/messages", "messages", params=params))
        return [Message.model_validate(row) for row in page.value], page.next_link

    async def list_recent_messages(self, limit=10):
        if not 1 <= limit <= 50:
            raise ValueError("Recent messages must be bounded to 1-50")
        return await self._messages({"$top": limit, "$select": SELECT, "$orderby": "receivedDateTime desc"})

    async def search_messages(self, query, limit=10):
        if not 1 <= limit <= 50 or not query.strip() or len(query) > 300 or any(c in query for c in '"\r\n'):
            raise ValueError("Invalid bounded search")
        return await self._messages({"$search": '"' + query + '"', "$top": limit, "$select": SELECT})

    async def get_conversation_messages(self, conversation_id, limit=25):
        if not 1 <= limit <= 50:
            raise ValueError("Conversation result bound required")
        return await self._messages({"$filter": "conversationId eq '" + conversation_id.replace("'", "''") + "'",
                                     "$top": limit, "$select": SELECT})

    async def get_attachments(self, message_id):
        page = GraphPage.model_validate(await self._request("GET",
            "/v1.0/me/messages/" + self.identifier(message_id) + "/attachments", "attachments",
            params={"$select": "id,name,contentType,size,isInline", "$top": 50}))
        return [Attachment.model_validate(row) for row in page.value], page.next_link

    async def download_attachment(self, message_id, attachment):
        if attachment.odata_type != "#microsoft.graph.fileAttachment" or attachment.size > 10_000_000:
            raise PermissionError("Only bounded file attachments are supported; no reference/item downloads")
        return await self._request("GET", "/v1.0/me/messages/" + self.identifier(message_id) +
                                  "/attachments/" + self.identifier(attachment.id) + "/$value",
                                  "attachment_download", binary=True)

    async def delta_page(self, folder_id="inbox", cursor=None):
        path = "/v1.0/me/mailFolders/" + self.identifier(folder_id) + "/messages/delta"
        target = self.cursor(cursor, path) if cursor else path
        page = GraphPage.model_validate(await self._request("GET", target, "delta",
                                            params=None if cursor else {"$select": SELECT, "$top": 25}))
        for link in (page.next_link, page.delta_link):
            if link:
                self.cursor(link, path)
        if bool(page.next_link) == bool(page.delta_link):
            raise GraphError("invalid_delta_checkpoint")
        return page

    async def _draft(self, payload, message_id=None, kind="new"):
        body = payload.model_dump(exclude={"grounding_hash", "template"})
        if kind == "new":
            path = "/v1.0/me/messages"
        else:
            path = "/v1.0/me/messages/" + self.identifier(message_id) + (
                "/createReply" if kind == "reply" else "/createForward")
            body = {"comment": payload.body.content}
            if kind == "forward":
                body["toRecipients"] = [r.model_dump() for r in payload.toRecipients]
        raw = await self._request("POST", path, "draft_" + kind, body=body, draft=True)
        try:
            result = Message.model_validate(raw)
        except ValidationError:
            raise GraphError("draft_result_unverified", uncertain=True) from None
        if not result.isDraft:
            raise GraphError("draft_result_unverified", uncertain=True)
        return result

    async def create_draft(self, payload):
        return await self._draft(payload)

    async def create_reply_draft(self, message_id, payload):
        return await self._draft(payload, message_id, "reply")

    async def create_forward_draft(self, message_id, payload):
        return await self._draft(payload, message_id, "forward")

    async def send_message(self, *args, **kwargs):
        raise PermissionError("APPROVAL_REQUIRED; production sending is not enabled")

    send_reply = send_message
    send_forward = send_message


OutlookAdapter = MicrosoftGraphMailAdapter
