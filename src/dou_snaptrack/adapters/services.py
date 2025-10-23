from __future__ import annotations


def get_edition_runner():
    try:
        from dou_utils.services.edition_runner_service import EditionRunnerService, EditionRunParams  # type: ignore
        return EditionRunnerService, EditionRunParams
    except Exception as e:  # pragma: no cover - optional dependency at runtime
        raise RuntimeError(f"EditionRunnerService indisponível: {e}")

def get_plan_from_map_service():
    try:
        from dou_utils.services.planning_service import PlanFromMapService  # type: ignore
        return PlanFromMapService
    except Exception as e:  # pragma: no cover
        raise RuntimeError(f"Serviço de planejamento indisponível: {e}")
