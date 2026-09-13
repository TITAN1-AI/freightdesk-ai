from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

OPERATIONS = ('ASCEND_GET_SESSION_STATE', 'ASCEND_GET_ACTIVE_LOADS', 'ASCEND_FIND_LOAD',
    'ASCEND_OPEN_LOAD_READONLY', 'ASCEND_READ_LOAD', 'ASCEND_READ_STOPS', 'ASCEND_READ_ASSIGNMENT')


class ReadCommand(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    version: Literal[1] = 1
    request_id: str = Field(min_length=32, max_length=32, pattern=r'^[a-f0-9]{32}$')
    operation: Literal['ASCEND_GET_SESSION_STATE', 'ASCEND_GET_ACTIVE_LOADS', 'ASCEND_FIND_LOAD',
        'ASCEND_OPEN_LOAD_READONLY', 'ASCEND_READ_LOAD', 'ASCEND_READ_STOPS', 'ASCEND_READ_ASSIGNMENT']
    load_id: str | None = Field(default=None, min_length=1, max_length=20, pattern=r'^[0-9]{1,20}$')
    tenant_id: Literal['booking-logistics'] = 'booking-logistics'
    actor: Literal['FreightDesk/Avery'] = 'FreightDesk/Avery'
    expected_revision: str | None = Field(default=None, min_length=64, max_length=64, pattern=r'^[a-f0-9]{64}$')

    @field_validator('version', mode='before')
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError('unsupported_protocol')
        return value

    @model_validator(mode='after')
    def scoped_read(self):
        scoped = self.operation not in OPERATIONS[:2]
        if scoped and (self.load_id is None or self.expected_revision is None):
            raise ValueError('load_and_board_revision_required')
        if not scoped and self.load_id is not None:
            raise ValueError('unexpected_load_scope')
        return self
