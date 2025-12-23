from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable

import pytest
from scrapinghub import ScrapinghubClient

import scrapinghub_mcp.server as server


class DummyMCP:
    def __init__(self, name: str) -> None:
        self.name = name
        self.tool_registry: dict[str, Callable[..., Any]] = {}

    def tool(self, name: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            func_name = getattr(func, "__name__", "tool")
            self.tool_registry[name or func_name] = func
            return func

        return decorator


@dataclass
class LiveTools:
    tool_registry: dict[str, Callable[..., Any]]
    method_to_tool: dict[str, str]
    cache: dict[str, Any]

    def call(self, method_name: str, params: dict[str, Any] | None = None) -> Any:
        if method_name in self.cache:
            return self.cache[method_name]
        tool_name = self.method_to_tool[method_name]
        tool = self.tool_registry[tool_name]
        if params is None:
            result = tool()
        else:
            result = tool(params)
        self.cache[method_name] = result
        return result


def _require_api_key() -> str:
    live_flag = os.environ.get("SCRAPINGHUB_MCP_LIVE")
    if live_flag != "1":
        pytest.skip("Set SCRAPINGHUB_MCP_LIVE=1 to enable live integration tests.")
    api_key = os.environ.get("SCRAPINGHUB_API_KEY")
    if not api_key:
        pytest.skip("SCRAPINGHUB_API_KEY is not set for live integration test.")
    assert api_key is not None
    return api_key


def _build_live_tools() -> LiveTools:
    api_key = _require_api_key()
    client = ScrapinghubClient(api_key)
    mcp = DummyMCP("scrapinghub-mcp")
    non_mutating = server.load_non_mutating_operations()
    server.register_scrapinghub_tools(
        mcp,
        client,
        allow_mutate=False,
        non_mutating_operations=non_mutating,
    )
    method_to_tool = {spec.method_name: tool_name for tool_name, spec in server.TOOL_SPECS.items()}
    return LiveTools(tool_registry=mcp.tool_registry, method_to_tool=method_to_tool, cache={})


def _project_id(live_tools: LiveTools) -> int:
    override = os.environ.get("SCRAPINGHUB_PROJECT_ID")
    if override:
        return int(override)
    result = live_tools.call("projects.list")
    project_ids = result.model_dump().get("items", [])
    if not project_ids:
        pytest.skip("No Scrapinghub projects available for live integration test.")
    return int(project_ids[0])


def _first_string(items: list[Any], *, keys: tuple[str, ...] = ()) -> str | None:
    for item in items:
        if isinstance(item, str) and item.strip():
            return item
        if isinstance(item, dict):
            for key in keys:
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    return value
    return None


def _first_collection(items: list[Any]) -> tuple[str, str] | None:
    for item in items:
        if isinstance(item, dict):
            name = item.get("name") or item.get("key")
            type_value = item.get("type") or item.get("collection_type")
            if isinstance(name, str) and isinstance(type_value, str):
                if name.strip() and type_value.strip():
                    return type_value, name
    return None


def _first_job_key(items: list[Any]) -> str | None:
    for item in items:
        if isinstance(item, dict):
            for key in ("key", "job_key"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    return value
    return None


def test_live_non_mutating_registration() -> None:
    live_tools = _build_live_tools()
    non_mutating = server.load_non_mutating_operations()

    for method_name in non_mutating:
        tool_name = live_tools.method_to_tool[method_name]
        assert tool_name in live_tools.tool_registry


def test_live_projects_endpoints() -> None:
    live_tools = _build_live_tools()

    live_tools.call("projects.list")
    live_tools.call("projects.summary")
    live_tools.call("projects.iter")


def test_live_project_scoped_endpoints() -> None:
    live_tools = _build_live_tools()
    project_id = _project_id(live_tools)

    params = {"project_id": project_id}
    live_tools.call("project.jobs.list", params)
    live_tools.call("project.jobs.iter", params)
    live_tools.call("project.jobs.count", params)
    live_tools.call("project.jobs.summary", params)
    live_tools.call("project.jobs.iter_last", params)
    live_tools.call("project.spiders.list", params)
    live_tools.call("project.spiders.iter", params)
    live_tools.call("project.activity.list", params)
    live_tools.call("project.activity.iter", params)
    live_tools.call("project.collections.list", params)
    live_tools.call("project.collections.iter", params)
    live_tools.call("project.frontiers.list", params)
    live_tools.call("project.frontiers.iter", params)
    live_tools.call("project.settings.list", params)
    live_tools.call("project.settings.iter", params)
    live_tools.call("projects.get", params)
    live_tools.call("get_project", params)


def test_live_job_detail_endpoints() -> None:
    live_tools = _build_live_tools()
    project_id = _project_id(live_tools)

    override = os.environ.get("SCRAPINGHUB_JOB_KEY")
    job_key = override
    if not job_key:
        result = live_tools.call("project.jobs.list", {"project_id": project_id})
        job_key = _first_job_key(result.model_dump().get("items", []))
    if not job_key:
        pytest.skip("No job key available for live job detail tests.")

    live_tools.call("get_job", {"job_key": job_key})
    live_tools.call("project.jobs.get", {"project_id": project_id, "job_key": job_key})


def test_live_collection_detail_endpoints() -> None:
    live_tools = _build_live_tools()
    project_id = _project_id(live_tools)

    name_override = os.environ.get("SCRAPINGHUB_COLLECTION_NAME")
    type_override = os.environ.get("SCRAPINGHUB_COLLECTION_TYPE")
    collection_name = name_override
    collection_type = type_override

    if not collection_name or not collection_type:
        result = live_tools.call("project.collections.list", {"project_id": project_id})
        collection = _first_collection(result.model_dump().get("items", []))
        if collection:
            collection_type, collection_name = collection

    if not collection_name or not collection_type:
        pytest.skip("No collection info available for live collection detail tests.")

    live_tools.call(
        "project.collections.get",
        {"project_id": project_id, "type_": collection_type, "name": collection_name},
    )
    name_params = {"project_id": project_id, "name": collection_name}
    live_tools.call("project.collections.get_store", name_params)
    live_tools.call("project.collections.get_cached_store", name_params)
    live_tools.call("project.collections.get_versioned_store", name_params)
    live_tools.call("project.collections.get_versioned_cached_store", name_params)


def test_live_frontier_detail_endpoints() -> None:
    live_tools = _build_live_tools()
    project_id = _project_id(live_tools)

    frontier_name = os.environ.get("SCRAPINGHUB_FRONTIER")
    if not frontier_name:
        result = live_tools.call("project.frontiers.list", {"project_id": project_id})
        frontier_name = _first_string(result.model_dump().get("items", []))

    if not frontier_name:
        pytest.skip("No frontier name available for live frontier detail tests.")

    live_tools.call("project.frontiers.get", {"project_id": project_id, "name": frontier_name})


def test_live_settings_get_endpoint() -> None:
    live_tools = _build_live_tools()
    project_id = _project_id(live_tools)

    setting_key = os.environ.get("SCRAPINGHUB_SETTING_KEY")
    if not setting_key:
        result = live_tools.call("project.settings.list", {"project_id": project_id})
        setting_key = _first_string(result.model_dump().get("items", []), keys=("key",))

    if not setting_key:
        pytest.skip("No setting key available for live settings get test.")

    live_tools.call("project.settings.get", {"project_id": project_id, "key": setting_key})


def test_live_spider_get_endpoint() -> None:
    live_tools = _build_live_tools()
    project_id = _project_id(live_tools)

    spider_name = os.environ.get("SCRAPINGHUB_SPIDER")
    if not spider_name:
        result = live_tools.call("project.spiders.list", {"project_id": project_id})
        spider_name = _first_string(result.model_dump().get("items", []))

    if not spider_name:
        pytest.skip("No spider name available for live spider get test.")

    live_tools.call("project.spiders.get", {"project_id": project_id, "spider": spider_name})
