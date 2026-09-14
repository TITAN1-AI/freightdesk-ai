"""Exact packaged runtime/document handshake; unrelated to durable enrollment generation."""
from typing import Literal
from pydantic import Field, field_validator
from executors.ascend_extension.controller import Strict

BUILD = dict(extension_version="0.6.4", controller_revision=3, native_protocol=1, content_protocol=3)

class BridgeBuild(Strict):
    extension_version: Literal["0.6.4"]
    controller_revision: Literal[3]
    native_protocol: Literal[1]
    content_protocol: Literal[3]

    @field_validator("controller_revision", "native_protocol", "content_protocol", mode="before")
    @classmethod
    def exact_integer(cls, value):
        if type(value) is not int:
            raise ValueError("PROTOCOL_VERSION_MISMATCH")
        return value

class DocumentHandshake(BridgeBuild):
    service_worker_version: Literal["0.6.4"]
    content_script_version: Literal["0.6.4"]
    document_generation: int = Field(ge=1)
    tab_id: int = Field(ge=0)
    document_id: str = Field(pattern=r"^[a-f0-9]{32}$")
