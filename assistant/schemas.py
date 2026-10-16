from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class Fact(BaseModel):
    topic: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=500)
    evidence: str = Field(min_length=1, max_length=500)


class Extraction(BaseModel):
    facts: list[Fact] = Field(default_factory=list, max_length=3)


class Observation(BaseModel):
    scene: str = Field(max_length=900)
    event: str = Field(max_length=200)
    remark: str = Field(max_length=250)
    significance: Literal['none', 'minor', 'major'] = 'none'
    event_key: str = Field(default='', max_length=100)
    confidence: float = Field(default=0, ge=0, le=1)


class FactInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    topic: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=500)
    kind: Literal['fact', 'profile', 'task'] = 'fact'
    active: bool = True


class ProfileInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    address: str = Field(max_length=100, default='')
    room: str = Field(max_length=500, default='')
    interests: str = Field(max_length=500, default='')


class Summary(BaseModel):
    text: str = Field(max_length=1800)


class ASRComparison(BaseModel):
    audio: str = Field(min_length=1, max_length=1280000)
    reference: str = Field(min_length=1, max_length=1000)
    language: Literal['auto', 'uk', 'ru', 'fr'] = 'auto'
