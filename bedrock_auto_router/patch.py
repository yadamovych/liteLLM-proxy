"""LiteLLM Router monkey-patch to register BedrockAutoRouter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from litellm.router import Router

from .router import BedrockAutoRouter

if TYPE_CHECKING:
    from litellm.types.router import Deployment


def _init_bedrock_auto_router(self: Router, deployment: Deployment) -> None:
    complexity_router_config: dict | None = deployment.litellm_params.complexity_router_config
    default_model: str | None = deployment.litellm_params.complexity_router_default_model

    if default_model is None and complexity_router_config:
        tiers = complexity_router_config.get("tiers", {})
        default_model = tiers.get("MEDIUM") or tiers.get("SIMPLE")

    if default_model is None:
        raise ValueError("complexity_router_default_model is required for bedrock-auto")

    router = BedrockAutoRouter(
        model_name=deployment.model_name,
        default_model=default_model,
        litellm_router_instance=self,
        complexity_router_config=complexity_router_config,
    )
    if deployment.model_name in self.complexity_routers:
        raise ValueError(f"Complexity-router deployment {deployment.model_name} already exists")
    self.complexity_routers[deployment.model_name] = router


def apply_patch() -> None:
    if getattr(Router.init_complexity_router_deployment, "_bedrock_auto_patched", False):
        return
    Router.init_complexity_router_deployment = _init_bedrock_auto_router  # type: ignore[method-assign]
    Router.init_complexity_router_deployment._bedrock_auto_patched = True  # type: ignore[attr-defined]
