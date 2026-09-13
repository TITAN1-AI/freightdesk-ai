from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class GraphModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class EmailAddress(GraphModel):
    address: str
    name: str | None = None


class Recipient(GraphModel):
    emailAddress: EmailAddress


class Body(GraphModel):
    contentType: str = "text"
    content: str = Field(default="", max_length=500_000, repr=False)


class Attachment(GraphModel):
    id: str
    name: str = ""
    contentType: str | None = None
    size: int = Field(default=0, ge=0)
    isInline: bool = False
    odata_type: str = Field(default="", alias="@odata.type")


class Message(GraphModel):
    id: str
    conversationId: str | None = None
    internetMessageId: str | None = None
    changeKey: str | None = None
    subject: str = Field(default="", max_length=10_000, repr=False)
    sender: Recipient | None = None
    from_: Recipient | None = Field(default=None, alias="from")
    toRecipients: list[Recipient] = Field(default_factory=list)
    ccRecipients: list[Recipient] = Field(default_factory=list)
    receivedDateTime: AwareDatetime | None = None
    lastModifiedDateTime: AwareDatetime | None = None
    body: Body = Field(default_factory=Body)
    hasAttachments: bool = False
    attachments: list[Attachment] = Field(default_factory=list)
    isDraft: bool = False


class MailboxProfile(GraphModel):
    id: str
    mail: str | None = None
    userPrincipalName: str | None = None
    displayName: str | None = None


class MailFolder(GraphModel):
    id: str
    displayName: str
    childFolderCount: int = 0
    totalItemCount: int = 0


class MailboxLocale(BaseModel):
    model_config = ConfigDict(extra="ignore")
    locale: str | None = Field(default=None, max_length=100)
    displayName: str | None = Field(default=None, max_length=200)


class MailboxSettings(BaseModel):
    # Keep only requested interpretation hints; discard automatic-reply text/other settings.
    model_config = ConfigDict(extra="ignore")
    timeZone: str | None = Field(default=None, max_length=200)
    language: MailboxLocale | None = None
    dateFormat: str | None = Field(default=None, max_length=100)
    timeFormat: str | None = Field(default=None, max_length=100)


class GraphPage(GraphModel):
    value: list[dict]
    next_link: str | None = Field(default=None, alias="@odata.nextLink", repr=False)
    delta_link: str | None = Field(default=None, alias="@odata.deltaLink", repr=False)


class DraftPayload(GraphModel):
    # Constructed by the server's grounded-draft service, not an email instruction.
    subject: str = Field(max_length=300)
    body: Body
    toRecipients: list[Recipient] = Field(min_length=1, max_length=10)
    grounding_hash: str = Field(exclude=True)
    template: Literal["acknowledgement", "verified_status"]
