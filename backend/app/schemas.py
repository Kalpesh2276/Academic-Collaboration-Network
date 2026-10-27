"""Pydantic request models (server-side validation for every write)."""
from __future__ import annotations

import re
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$")

EntityId = Annotated[str, StringConstraints(strip_whitespace=True, pattern=ID_PATTERN)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]
Year = Annotated[int, Field(ge=1900, le=2100)]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _dedupe(values: Optional[list[str]]) -> Optional[list[str]]:
    if values is None:
        return None
    seen, out = set(), []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


# ---------------------------------------------------------------- Researcher
class ResearcherCreate(_Base):
    researcherId: Optional[EntityId] = None  # generated (R041, ...) when omitted
    name: Name
    email: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, max_length=200)]
    specialization: ShortText
    experienceYears: Annotated[int, Field(ge=0, le=70)]
    institutionId: Optional[EntityId] = None
    departmentId: Optional[EntityId] = None
    role: Optional[ShortText] = None

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        if not EMAIL_PATTERN.match(v):
            raise ValueError("must be a valid e-mail address")
        return v

    @model_validator(mode="after")
    def _dept_needs_inst(self):
        if self.departmentId and not self.institutionId:
            raise ValueError("departmentId requires institutionId (a department belongs to an institution)")
        return self


class ResearcherUpdate(_Base):
    name: Optional[Name] = None
    email: Optional[Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, max_length=200)]] = None
    specialization: Optional[ShortText] = None
    experienceYears: Optional[Annotated[int, Field(ge=0, le=70)]] = None
    institutionId: Optional[EntityId] = None
    departmentId: Optional[EntityId] = None
    role: Optional[ShortText] = None

    @field_validator("email")
    @classmethod
    def _email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not EMAIL_PATTERN.match(v):
            raise ValueError("must be a valid e-mail address")
        return v


# ---------------------------------------------------------------- Paper
class PaperCreate(_Base):
    paperId: Optional[EntityId] = None
    title: Name
    publicationYear: Year
    abstract: LongText = ""
    doi: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]] = None
    authorIds: list[EntityId] = Field(min_length=1, max_length=50)
    topicIds: list[EntityId] = Field(default_factory=list, max_length=20)
    conferenceId: Optional[EntityId] = None
    journalId: Optional[EntityId] = None
    citedPaperIds: list[EntityId] = Field(default_factory=list, max_length=200)

    @field_validator("doi")
    @classmethod
    def _doi(cls, v: Optional[str]) -> Optional[str]:
        if v in (None, ""):
            return None
        if not DOI_PATTERN.match(v):
            raise ValueError("DOI must look like 10.1234/some-suffix")
        return v

    @field_validator("authorIds", "topicIds", "citedPaperIds")
    @classmethod
    def _unique(cls, v: list[str]) -> list[str]:
        return _dedupe(v) or []


class PaperUpdate(_Base):
    """Fields left out (None) are unchanged. A provided list REPLACES the existing links."""

    title: Optional[Name] = None
    publicationYear: Optional[Year] = None
    abstract: Optional[LongText] = None
    doi: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]] = None
    authorIds: Optional[list[EntityId]] = Field(default=None, min_length=1, max_length=50)
    topicIds: Optional[list[EntityId]] = Field(default=None, max_length=20)
    conferenceId: Optional[str] = None  # "" removes the conference link
    journalId: Optional[str] = None  # "" removes the journal link
    citedPaperIds: Optional[list[EntityId]] = Field(default=None, max_length=200)

    @field_validator("doi")
    @classmethod
    def _doi(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        if not DOI_PATTERN.match(v):
            raise ValueError("DOI must look like 10.1234/some-suffix")
        return v

    @field_validator("authorIds", "topicIds", "citedPaperIds")
    @classmethod
    def _unique(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        return _dedupe(v)

    @field_validator("conferenceId", "journalId")
    @classmethod
    def _venue(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        if not re.match(ID_PATTERN, v):
            raise ValueError("invalid identifier")
        return v


# ---------------------------------------------------------------- Simple entities
class InstitutionCreate(_Base):
    institutionId: Optional[EntityId] = None
    name: Name
    location: ShortText
    type: ShortText


class InstitutionUpdate(_Base):
    name: Optional[Name] = None
    location: Optional[ShortText] = None
    type: Optional[ShortText] = None


class DepartmentCreate(_Base):
    departmentId: Optional[EntityId] = None
    name: Name
    institutionId: EntityId


class DepartmentUpdate(_Base):
    name: Optional[Name] = None


class TopicCreate(_Base):
    topicId: Optional[EntityId] = None
    name: ShortText
    description: LongText = ""


class TopicUpdate(_Base):
    name: Optional[ShortText] = None
    description: Optional[LongText] = None


class ConferenceCreate(_Base):
    conferenceId: Optional[EntityId] = None
    name: ShortText
    year: Year
    location: ShortText


class ConferenceUpdate(_Base):
    name: Optional[ShortText] = None
    year: Optional[Year] = None
    location: Optional[ShortText] = None


class JournalCreate(_Base):
    journalId: Optional[EntityId] = None
    name: Name
    publisher: ShortText
    field: Optional[ShortText] = None


class JournalUpdate(_Base):
    name: Optional[Name] = None
    publisher: Optional[ShortText] = None
    field: Optional[ShortText] = None


class CollaborationCreate(_Base):
    researcherA: EntityId
    researcherB: EntityId
    since: Optional[Year] = None

    @model_validator(mode="after")
    def _not_self(self):
        if self.researcherA == self.researcherB:
            raise ValueError("a researcher cannot collaborate with themselves")
        return self
