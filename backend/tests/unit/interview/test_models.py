from __future__ import annotations

import uuid

from hiresense.interview.domain.models import Competency, Story


def test_competency_enum_values() -> None:
    assert Competency.LEADERSHIP.value == "leadership"
    assert Competency.PROBLEM_SOLVING.value == "problem_solving"
    assert Competency.COLLABORATION.value == "collaboration"
    assert Competency.COMMUNICATION.value == "communication"
    assert Competency.ADAPTABILITY.value == "adaptability"
    assert Competency.TECHNICAL.value == "technical"
    assert Competency.INITIATIVE.value == "initiative"
    assert Competency.CONFLICT_RESOLUTION.value == "conflict_resolution"


def test_competency_enum_count() -> None:
    assert len(Competency) == 8


def test_competency_is_str_subclass() -> None:
    assert isinstance(Competency.LEADERSHIP, str)
    assert Competency.LEADERSHIP == "leadership"


def test_story_creation_minimal() -> None:
    story = Story(
        title="Led a cross-functional team",
        competency=Competency.LEADERSHIP.value,
        situation="We had a critical deadline",
        task="Coordinate 5 engineers",
        action="Held daily standups and unblocked dependencies",
        result="Shipped on time with zero defects",
    )
    assert story.title == "Led a cross-functional team"
    assert story.competency == Competency.LEADERSHIP.value
    assert story.reflection is None
    assert story.tags is None


def test_story_creation_full() -> None:
    story_id = uuid.uuid4()
    story = Story(
        id=story_id,
        title="Resolved production outage",
        competency=Competency.PROBLEM_SOLVING.value,
        situation="Database went down at 2am",
        task="Restore service within SLA",
        action="Identified root cause, rolled back migration",
        result="99.9% uptime preserved",
        reflection="Add better alerting",
        tags="production,database,on-call",
    )
    assert story.id == story_id
    assert story.reflection == "Add better alerting"
    assert story.tags == "production,database,on-call"
