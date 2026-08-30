"""The agent's action union.

Exception to the one-definition-per-file rule: the variants and the
discriminated union that binds them are a single cohesive type, and Pydantic's
Field(discriminator=...) requires them co-located to resolve.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field

from hiresense.submission.domain.field_answer import FieldAnswer


class FillFieldsAction(BaseModel):
    kind: Literal["fill_fields"] = "fill_fields"
    fills: list[FieldAnswer]


class ClickAction(BaseModel):
    kind: Literal["click"] = "click"
    selector: str


class NavigateAction(BaseModel):
    kind: Literal["navigate"] = "navigate"
    url: str


class UploadFileAction(BaseModel):
    kind: Literal["upload_file"] = "upload_file"
    selector: str
    artifact: Literal["cv", "cover_letter"]


class SubmitAction(BaseModel):
    kind: Literal["submit"] = "submit"
    selector: str
    dry_run: bool = True


class EscalateAction(BaseModel):
    kind: Literal["escalate"] = "escalate"
    reason: str
    fields: list[str] = Field(default_factory=list)


class DoneAction(BaseModel):
    kind: Literal["done"] = "done"
    evidence: dict[str, Any] = Field(default_factory=dict)


AgentAction = Annotated[
    Union[
        FillFieldsAction,
        ClickAction,
        NavigateAction,
        UploadFileAction,
        SubmitAction,
        EscalateAction,
        DoneAction,
    ],
    Field(discriminator="kind"),
]
