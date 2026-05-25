from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from hiresense.admin.api.dependencies import get_llm_settings_service, require_admin
from hiresense.admin.api.schemas import (
    FeatureOverrideRequest,
    FeatureOverrideTestRequest,
    FeatureView,
    LLMSettingsTestRequest,
    LLMSettingsUpdateRequest,
    LLMSettingsView,
    LLMTestResult,
)
from hiresense.admin.domain.llm_settings_service import LLMSettingsService, LLMSettingsServiceError

router = APIRouter(
    prefix="/admin/llm-settings",
    tags=["admin", "llm-settings"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=LLMSettingsView)
def get_settings(
    service: Annotated[LLMSettingsService, Depends(get_llm_settings_service)],
) -> LLMSettingsView:
    view = service.get_global_view()
    return LLMSettingsView(
        provider=view.provider,
        model=view.model,
        api_key_mask=view.api_key_mask,
        has_stored_key=view.has_stored_key,
        extra_params=view.extra_params,
        updated_by=view.updated_by,
        updated_at=view.updated_at_iso,
        source=view.source,
    )


@router.put("", response_model=LLMSettingsView)
async def update_settings(
    body: LLMSettingsUpdateRequest,
    service: Annotated[LLMSettingsService, Depends(get_llm_settings_service)],
    actor: Annotated[str, Depends(require_admin)],
) -> LLMSettingsView:
    try:
        view = await service.update_global_config(
            provider=body.provider,
            model=body.model,
            api_key=body.api_key,
            extra_params=body.extra_params,
            actor=actor,
            skip_test=body.skip_test,
        )
    except LLMSettingsServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return LLMSettingsView(
        provider=view.provider,
        model=view.model,
        api_key_mask=view.api_key_mask,
        has_stored_key=view.has_stored_key,
        extra_params=view.extra_params,
        updated_by=view.updated_by,
        updated_at=view.updated_at_iso,
        source=view.source,
    )


@router.post("/test", response_model=LLMTestResult)
async def test_settings(
    body: LLMSettingsTestRequest,
    service: Annotated[LLMSettingsService, Depends(get_llm_settings_service)],
) -> LLMTestResult:
    result = await service.test_global_config(
        provider=body.provider,
        model=body.model,
        api_key=body.api_key,
        extra_params=body.extra_params,
    )
    return LLMTestResult(
        success=result.success,
        latency_ms=result.latency_ms,
        response_preview=result.response_preview,
        error=result.error,
    )


# ---- Per-feature overrides ----------------------------------------


@router.get("/overrides", response_model=list[FeatureView])
def list_overrides(
    service: Annotated[LLMSettingsService, Depends(get_llm_settings_service)],
) -> list[FeatureView]:
    return [_to_feature_view(v) for v in service.list_effective_features()]


@router.put("/overrides/{feature_key}", response_model=FeatureView)
async def upsert_override(
    feature_key: str,
    body: FeatureOverrideRequest,
    service: Annotated[LLMSettingsService, Depends(get_llm_settings_service)],
    actor: Annotated[str, Depends(require_admin)],
) -> FeatureView:
    try:
        view = await service.set_override(
            feature_key=feature_key,
            provider=body.provider,
            model=body.model,
            extra_params=body.extra_params,
            actor=actor,
            skip_test=body.skip_test,
        )
    except LLMSettingsServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _to_feature_view(view)


@router.delete("/overrides/{feature_key}", response_model=FeatureView)
def clear_override(
    feature_key: str,
    service: Annotated[LLMSettingsService, Depends(get_llm_settings_service)],
    actor: Annotated[str, Depends(require_admin)],
) -> FeatureView:
    try:
        view = service.clear_override(feature_key=feature_key, actor=actor)
    except LLMSettingsServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _to_feature_view(view)


@router.post("/overrides/{feature_key}/test", response_model=LLMTestResult)
async def test_override(
    feature_key: str,
    body: FeatureOverrideTestRequest,
    service: Annotated[LLMSettingsService, Depends(get_llm_settings_service)],
) -> LLMTestResult:
    result = await service.test_override(
        feature_key=feature_key,
        provider=body.provider,
        model=body.model,
        extra_params=body.extra_params,
    )
    return LLMTestResult(
        success=result.success,
        latency_ms=result.latency_ms,
        response_preview=result.response_preview,
        error=result.error,
    )


def _to_feature_view(v) -> FeatureView:
    return FeatureView(
        feature_key=v.feature_key,
        feature_name=v.feature_name,
        feature_description=v.feature_description,
        provider=v.provider,
        model=v.model,
        inherits_provider=v.inherits_provider,
        inherits_model=v.inherits_model,
        extra_params=v.extra_params,
        source=v.source,
    )
