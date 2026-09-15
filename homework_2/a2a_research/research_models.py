"""Typed domain payloads for the literature search workflow."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PaperRecord(BaseModel):
    """One reproducible record from the checked-in demo corpus."""

    paper_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    authors: list[str] = Field(min_length=1)
    year: int = Field(ge=1900, le=2100)
    keywords: list[str] = Field(min_length=1)
    abstract: str = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)
    source: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class SearchRequest(BaseModel):
    """Payload accepted by the Literature Search Agent."""

    task: Literal["search"]
    question: str = Field(min_length=3)
    top_k: int = Field(default=3, ge=1, le=10)

    model_config = ConfigDict(extra="forbid")


class SearchHit(BaseModel):
    """A ranked paper returned to the next agent in the workflow."""

    paper_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    authors: list[str] = Field(min_length=1)
    year: int = Field(ge=1900, le=2100)
    score: int = Field(ge=1)
    abstract: str = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)
    source: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class SearchResponse(BaseModel):
    """Structured result sent by the Literature Search Agent."""

    task: Literal["search.result"] = "search.result"
    question: str = Field(min_length=3)
    hits: list[SearchHit]

    model_config = ConfigDict(extra="forbid")
