import re
from pydantic import field_validator
from pydantic import BaseModel, ConfigDict
from datetime import datetime


from enum import Enum

class EventType(str, Enum):
    document_uploaded = "document_uploaded"
    new_conversation = "new_conversation"
    delete_conversation = "delete_conversation"

class WebhookCreate(BaseModel):
    url: str
    event_type: EventType


class Prompt(BaseModel):
    content: str

    model_config = ConfigDict(from_attributes=True)



class UserCreate(BaseModel):
    username: str
    password: str

    @field_validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('password must be at least 8 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('password must contain at least one number')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('password must contain at least one spacial character')
        return v

# @field_validator('username')
# def validate_username(cls, v):
#     if not re.match(r'^[a-zA-Z0-9_]{3,20}$', v):
#         raise ValueError('username must be 3-20 characters, only letters, numbers and underscores')
#     return v
#Minimum 8 characters
#At least 1 uppercase
#At least 1 lowercase
#At least 1 number
#At least 1 special character

class gemini(BaseModel):
    text: str

class TokenData(BaseModel):
    id: int | None = None
    is_admin: bool

class conversation(BaseModel):
    user_id: int
    title: str

class ConversationOut(BaseModel):
    id: int
    title: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)