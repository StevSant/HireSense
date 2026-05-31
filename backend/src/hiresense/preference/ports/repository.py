from __future__ import annotations

from typing import Protocol

from hiresense.preference.domain import FeedbackSignal, PreferenceModel


class PreferenceRepositoryPort(Protocol):
    def add_signal(self, signal: FeedbackSignal) -> FeedbackSignal: ...

    def list_signals(self) -> list[FeedbackSignal]: ...

    def get_model(self) -> PreferenceModel | None: ...

    def save_model(self, model: PreferenceModel) -> PreferenceModel: ...

    def clear(self) -> None: ...
