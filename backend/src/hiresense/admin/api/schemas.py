from __future__ import annotations

from pydantic import BaseModel, Field


# ---- LLM settings ---------------------------------------------------


class LLMSettingsView(BaseModel):
    provider: str
    model: str
    api_key_mask: str = Field("", description="Masked preview of the stored API key; never the plaintext.")
    has_stored_key: bool = False
    extra_params: dict = Field(default_factory=dict)
    updated_by: str | None = None
    updated_at: str | None = None
    source: str = "env"


class LLMSettingsUpdateRequest(BaseModel):
    provider: str
    model: str
    api_key: str | None = Field(
        default=None,
        description="Plaintext API key. Omit or null to leave the stored key unchanged.",
    )
    extra_params: dict = Field(default_factory=dict)
    skip_test: bool = False


class LLMSettingsTestRequest(BaseModel):
    provider: str
    model: str
    api_key: str | None = None
    extra_params: dict = Field(default_factory=dict)


class LLMTestResult(BaseModel):
    success: bool
    latency_ms: float
    response_preview: str
    error: str | None = None


# ---- Feature overrides ---------------------------------------------


class FeatureView(BaseModel):
    feature_key: str
    feature_name: str
    feature_description: str
    provider: str
    model: str
    inherits_provider: bool
    inherits_model: bool
    extra_params: dict = Field(default_factory=dict)
    source: str  # "inherited" | "override"


class FeatureOverrideRequest(BaseModel):
    provider: str | None = None
    model: str | None = None
    extra_params: dict = Field(default_factory=dict)
    skip_test: bool = False


class FeatureOverrideTestRequest(BaseModel):
    provider: str | None = None
    model: str | None = None
    extra_params: dict = Field(default_factory=dict)


# ---- Usage dashboard -----------------------------------------------


class UsageTotalsView(BaseModel):
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost_usd: float


class DashboardSummaryView(BaseModel):
    today: UsageTotalsView
    this_month: UsageTotalsView
    all_time: UsageTotalsView


class UsageBucketView(BaseModel):
    key: str
    calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float


class TimeseriesResponse(BaseModel):
    days: int
    buckets: list[UsageBucketView]


class BreakdownResponse(BaseModel):
    dimension: str
    days: int | None
    buckets: list[UsageBucketView]


class UsageCallView(BaseModel):
    id: str
    created_at: str
    feature_key: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: float
    success: bool
    error: str | None = None


class RecentCallsResponse(BaseModel):
    calls: list[UsageCallView]
    limit: int
    offset: int
