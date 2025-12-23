from __future__ import annotations

import json
import os
import sys
import tomllib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Callable, Protocol, TypeVar, cast

import jsonschema
import pydantic_core
import structlog
import yaml
from dotenv import load_dotenv
from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field
from requests import HTTPError
from scrapinghub import ScrapinghubClient


class MCPProtocol(Protocol):
    def __init__(self, name: str) -> None: ...

    def tool(
        self, name: str | None = None
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...


MCPType = TypeVar("MCPType", bound=MCPProtocol)


class HasModelDump(Protocol):
    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]: ...


class HasProjectId(HasModelDump, Protocol):
    project_id: int


API_KEY_ENV = "SCRAPINGHUB_API_KEY"
DOCS_URL = "https://github.com/lambdamechanic/scrapinghub-mcp"
ALLOWLIST_FILENAME = "scrapinghub-mcp.allowlist.yaml"
ALLOWLIST_SCHEMA_FILENAME = "allowlist-schema.json"
_ALLOWLIST_SCHEMA: dict[str, object] | None = None
logger = structlog.get_logger(__name__)


# TODO: Replace MCP-level schemas once scrapinghub.client.* exposes explicit type hints.
# These models are temporary shims to provide tight schemas until upstream adds
# typed params/returns.
JsonValue = dict[str, Any] | list[Any] | str | int | float | bool | None


class EmptyParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: int = Field(..., description="Scrapinghub project id.")


class ProjectsSummaryParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: str | list[str] | None = Field(
        default=None, description="Filter summaries by job state."
    )


class ProjectsGetParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: int = Field(..., description="Scrapinghub project id.")


class ProjectsIterParams(EmptyParams):
    pass


class JobsListParams(ProjectParams):
    count: int | None = None
    start: int | None = None
    spider: str | None = None
    state: str | list[str] | None = None
    has_tag: str | list[str] | None = None
    lacks_tag: str | list[str] | None = None
    startts: int | None = None
    endts: int | None = None
    meta: str | list[str] | None = None
    params: dict[str, JsonValue] | None = None


class JobsIterParams(JobsListParams):
    pass


class JobsCountParams(ProjectParams):
    spider: str | None = None
    state: str | list[str] | None = None
    has_tag: str | list[str] | None = None
    lacks_tag: str | list[str] | None = None
    startts: int | None = None
    endts: int | None = None
    params: dict[str, JsonValue] | None = None


class JobsSummaryParams(ProjectParams):
    state: str | list[str] | None = None
    spider: str | None = None
    params: dict[str, JsonValue] | None = None


class JobsIterLastParams(ProjectParams):
    start: int | None = None
    start_after: int | None = None
    count: int | None = None
    spider: str | None = None
    params: dict[str, JsonValue] | None = None


class JobsGetParams(ProjectParams):
    job_key: str = Field(
        ...,
        description="Job key in the form project_id/spider_id/job_id.",
        min_length=1,
    )


class JobsRunParams(ProjectParams):
    spider: str | None = None
    units: int | None = None
    priority: int | None = None
    meta: dict[str, JsonValue] | None = None
    add_tag: str | list[str] | None = None
    job_args: dict[str, JsonValue] | None = None
    job_settings: dict[str, JsonValue] | None = None
    cmd_args: str | None = None
    environment: dict[str, JsonValue] | None = None
    params: dict[str, JsonValue] | None = None


class JobsCancelParams(ProjectParams):
    keys: list[str] | None = None
    count: int | None = None
    params: dict[str, JsonValue] | None = None


class JobsUpdateTagsParams(ProjectParams):
    add: str | list[str] | None = None
    remove: str | list[str] | None = None
    spider: str | None = None


class SpidersGetParams(ProjectParams):
    spider: str = Field(..., description="Spider name or id.")
    params: dict[str, JsonValue] | None = None


class ActivityListParams(ProjectParams):
    params: dict[str, JsonValue] | None = None


class ActivityIterParams(ProjectParams):
    count: int | None = None
    params: dict[str, JsonValue] | None = None


class ActivityAddParams(ProjectParams):
    values: list[dict[str, JsonValue]] | dict[str, JsonValue]
    params: dict[str, JsonValue] | None = None


class CollectionsGetParams(ProjectParams):
    type_: str
    name: str


class CollectionsNameParams(ProjectParams):
    name: str


class FrontiersNameParams(ProjectParams):
    name: str


class SettingsKeyParams(ProjectParams):
    key: str


class SettingsSetParams(ProjectParams):
    key: str
    value: JsonValue


class SettingsUpdateParams(ProjectParams):
    values: dict[str, JsonValue]


class SettingsListParams(ProjectParams):
    params: dict[str, JsonValue] | None = None


class GetJobParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_key: str = Field(
        ...,
        description="Job key in the form project_id/spider_id/job_id.",
        min_length=1,
    )


class GetProjectParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: int = Field(..., description="Scrapinghub project id.")


class CloseClientParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timeout: float | None = None


class ListProjectsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[int]


class ProjectSummaryItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    project: int
    pending: int
    running: int
    finished: int
    has_capacity: bool


class ProjectSummaryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ProjectSummaryItem]


class GetJobResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_key: str
    project_id: int
    metadata: dict[str, JsonValue]


class GetProjectResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: int
    key: str


class ItemsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[JsonValue]


class ResultWrapper(BaseModel):
    model_config = ConfigDict(extra="forbid")
    result: JsonValue


class CountResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    count: int


class JobRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_key: str


class CloseClientResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    closed: bool


@dataclass(frozen=True)
class ToolSpec:
    method_name: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    output_builder: Callable[[Any], BaseModel]
    handler: Callable[[Any, BaseModel], Any]
    description: str


def _model_kwargs(params: HasModelDump, *, exclude: set[str]) -> dict[str, Any]:
    data = params.model_dump(exclude_none=True)
    extra = data.pop("params", None)
    for field in exclude:
        data.pop(field, None)
    if isinstance(extra, dict):
        merged = dict(extra)
        merged.update(data)
        return merged
    return data


def _to_jsonable(value: Any) -> JsonValue:
    try:
        return cast(JsonValue, pydantic_core.to_jsonable_python(value))
    except pydantic_core.PydanticSerializationError:
        return str(value)


def _collect_items(result: Any) -> list[Any]:
    if isinstance(result, dict):
        return [result]
    if isinstance(result, bytes):
        return [result.decode("utf-8", errors="replace")]
    if isinstance(result, str):
        return [result]
    if isinstance(result, list):
        return result
    if hasattr(result, "__iter__"):
        return list(result)
    return [result]


def _build_items_result(result: Any) -> BaseModel:
    items = [_to_jsonable(item) for item in _collect_items(result)]
    return ItemsResult(items=items)


def _build_result_wrapper(result: Any) -> BaseModel:
    return ResultWrapper(result=_to_jsonable(result))


def _build_count_result(result: Any) -> BaseModel:
    if isinstance(result, dict) and "count" in result:
        return CountResult(count=int(result["count"]))
    if isinstance(result, int):
        return CountResult(count=result)
    raise TypeError("Expected a count result.")


def _build_job_run_result(result: Any) -> BaseModel:
    job_key = getattr(result, "key", None)
    if not isinstance(job_key, str):
        raise TypeError("Expected a job object with key.")
    return JobRunResult(job_key=job_key)


def _build_list_projects_result(result: Any) -> BaseModel:
    if isinstance(result, (str, bytes, dict)):
        raise TypeError("Expected a list of project ids.")
    items = result if isinstance(result, list) else list(result)
    return ListProjectsResult(items=items)


def _build_project_summary_result(result: Any) -> BaseModel:
    if isinstance(result, dict):
        items = [result]
    elif isinstance(result, (str, bytes)):
        raise TypeError("Expected a list of summary objects.")
    elif isinstance(result, list):
        items = result
    elif hasattr(result, "__iter__"):
        items = list(result)
    else:
        items = [result]
    return ProjectSummaryResult(items=items)


def _build_get_job_result(result: Any) -> BaseModel:
    job_key = getattr(result, "key", None)
    project_id = getattr(result, "project_id", None)
    metadata = {}
    meta = getattr(result, "metadata", None)
    if meta is not None and hasattr(meta, "list"):
        metadata = dict(meta.list())
    if not isinstance(job_key, str) or project_id is None:
        raise TypeError("Expected a job object with key and project_id.")
    return GetJobResult(job_key=job_key, project_id=int(project_id), metadata=metadata)


def _build_get_project_result(result: Any) -> BaseModel:
    key = getattr(result, "key", None)
    if not isinstance(key, str):
        raise TypeError("Expected a project object with key.")
    project_id = int(key)
    return GetProjectResult(project_id=project_id, key=key)


def _build_close_client_result(_: Any) -> BaseModel:
    return CloseClientResult(closed=True)


def _call_client_method(client: Any, method_name: str, params: BaseModel) -> Any:
    method = getattr(client, method_name)
    kwargs = _model_kwargs(params, exclude=set())
    return method(**kwargs) if kwargs else method()


def _call_projects_method(client: Any, method_name: str, params: BaseModel) -> Any:
    method = getattr(client.projects, method_name)
    kwargs = _model_kwargs(params, exclude=set())
    return method(**kwargs) if kwargs else method()


def _call_project_method(
    client: Any, resource: str, method_name: str, params: HasProjectId
) -> Any:
    project = client.get_project(params.project_id)
    target = getattr(project, resource)
    method = getattr(target, method_name)
    kwargs = _model_kwargs(params, exclude={"project_id"})
    return method(**kwargs) if kwargs else method()


TOOL_SPECS: dict[str, ToolSpec] = {
    "list_projects": ToolSpec(
        method_name="projects.list",
        input_model=EmptyParams,
        output_model=ListProjectsResult,
        output_builder=_build_list_projects_result,
        handler=lambda client, params: _call_projects_method(client, "list", params),
        description="List available Scrapinghub project IDs.",
    ),
    "project_summary": ToolSpec(
        method_name="projects.summary",
        input_model=ProjectsSummaryParams,
        output_model=ProjectSummaryResult,
        output_builder=_build_project_summary_result,
        handler=lambda client, params: _call_projects_method(client, "summary", params),
        description="Return per-project job summaries, optionally filtered by state.",
    ),
    "projects_get": ToolSpec(
        method_name="projects.get",
        input_model=ProjectsGetParams,
        output_model=GetProjectResult,
        output_builder=_build_get_project_result,
        handler=lambda client, params: _call_projects_method(client, "get", params),
        description="Fetch a project handle by project id.",
    ),
    "projects_iter": ToolSpec(
        method_name="projects.iter",
        input_model=ProjectsIterParams,
        output_model=ItemsResult,
        output_builder=_build_items_result,
        handler=lambda client, params: _call_projects_method(client, "iter", params),
        description="Iterate available projects.",
    ),
    "get_job": ToolSpec(
        method_name="get_job",
        input_model=GetJobParams,
        output_model=GetJobResult,
        output_builder=_build_get_job_result,
        handler=lambda client, params: _call_client_method(client, "get_job", params),
        description="Fetch job metadata for a given job key.",
    ),
    "get_project": ToolSpec(
        method_name="get_project",
        input_model=GetProjectParams,
        output_model=GetProjectResult,
        output_builder=_build_get_project_result,
        handler=lambda client, params: _call_client_method(client, "get_project", params),
        description="Fetch a project handle by project id.",
    ),
    "close_client": ToolSpec(
        method_name="close",
        input_model=CloseClientParams,
        output_model=CloseClientResult,
        output_builder=_build_close_client_result,
        handler=lambda client, params: _call_client_method(client, "close", params),
        description="Close the underlying Scrapinghub client session.",
    ),
    "project_jobs_list": ToolSpec(
        method_name="project.jobs.list",
        input_model=JobsListParams,
        output_model=ItemsResult,
        output_builder=_build_items_result,
        handler=lambda client, params: _call_project_method(client, "jobs", "list", params),
        description="List jobs for a project.",
    ),
    "project_jobs_iter": ToolSpec(
        method_name="project.jobs.iter",
        input_model=JobsIterParams,
        output_model=ItemsResult,
        output_builder=_build_items_result,
        handler=lambda client, params: _call_project_method(client, "jobs", "iter", params),
        description="Iterate jobs for a project.",
    ),
    "project_jobs_count": ToolSpec(
        method_name="project.jobs.count",
        input_model=JobsCountParams,
        output_model=CountResult,
        output_builder=_build_count_result,
        handler=lambda client, params: _call_project_method(client, "jobs", "count", params),
        description="Count jobs for a project.",
    ),
    "project_jobs_summary": ToolSpec(
        method_name="project.jobs.summary",
        input_model=JobsSummaryParams,
        output_model=ItemsResult,
        output_builder=_build_items_result,
        handler=lambda client, params: _call_project_method(client, "jobs", "summary", params),
        description="Summarize jobs for a project.",
    ),
    "project_jobs_iter_last": ToolSpec(
        method_name="project.jobs.iter_last",
        input_model=JobsIterLastParams,
        output_model=ItemsResult,
        output_builder=_build_items_result,
        handler=lambda client, params: _call_project_method(client, "jobs", "iter_last", params),
        description="Iterate last jobs for each spider in a project.",
    ),
    "project_jobs_get": ToolSpec(
        method_name="project.jobs.get",
        input_model=JobsGetParams,
        output_model=GetJobResult,
        output_builder=_build_get_job_result,
        handler=lambda client, params: _call_project_method(client, "jobs", "get", params),
        description="Fetch a job for a project by key.",
    ),
    "project_jobs_run": ToolSpec(
        method_name="project.jobs.run",
        input_model=JobsRunParams,
        output_model=JobRunResult,
        output_builder=_build_job_run_result,
        handler=lambda client, params: _call_project_method(client, "jobs", "run", params),
        description="Schedule a job for a project.",
    ),
    "project_jobs_cancel": ToolSpec(
        method_name="project.jobs.cancel",
        input_model=JobsCancelParams,
        output_model=CountResult,
        output_builder=_build_count_result,
        handler=lambda client, params: _call_project_method(client, "jobs", "cancel", params),
        description="Cancel jobs for a project.",
    ),
    "project_jobs_update_tags": ToolSpec(
        method_name="project.jobs.update_tags",
        input_model=JobsUpdateTagsParams,
        output_model=CountResult,
        output_builder=_build_count_result,
        handler=lambda client, params: _call_project_method(client, "jobs", "update_tags", params),
        description="Update job tags for a project.",
    ),
    "project_spiders_list": ToolSpec(
        method_name="project.spiders.list",
        input_model=ProjectParams,
        output_model=ItemsResult,
        output_builder=_build_items_result,
        handler=lambda client, params: _call_project_method(client, "spiders", "list", params),
        description="List spiders for a project.",
    ),
    "project_spiders_iter": ToolSpec(
        method_name="project.spiders.iter",
        input_model=ProjectParams,
        output_model=ItemsResult,
        output_builder=_build_items_result,
        handler=lambda client, params: _call_project_method(client, "spiders", "iter", params),
        description="Iterate spiders for a project.",
    ),
    "project_spiders_get": ToolSpec(
        method_name="project.spiders.get",
        input_model=SpidersGetParams,
        output_model=ResultWrapper,
        output_builder=_build_result_wrapper,
        handler=lambda client, params: _call_project_method(client, "spiders", "get", params),
        description="Fetch a spider by name or id.",
    ),
    "project_activity_list": ToolSpec(
        method_name="project.activity.list",
        input_model=ActivityListParams,
        output_model=ItemsResult,
        output_builder=_build_items_result,
        handler=lambda client, params: _call_project_method(client, "activity", "list", params),
        description="List activity for a project.",
    ),
    "project_activity_iter": ToolSpec(
        method_name="project.activity.iter",
        input_model=ActivityIterParams,
        output_model=ItemsResult,
        output_builder=_build_items_result,
        handler=lambda client, params: _call_project_method(client, "activity", "iter", params),
        description="Iterate activity for a project.",
    ),
    "project_activity_add": ToolSpec(
        method_name="project.activity.add",
        input_model=ActivityAddParams,
        output_model=ResultWrapper,
        output_builder=_build_result_wrapper,
        handler=lambda client, params: _call_project_method(client, "activity", "add", params),
        description="Add activity records to a project.",
    ),
    "project_collections_list": ToolSpec(
        method_name="project.collections.list",
        input_model=ProjectParams,
        output_model=ItemsResult,
        output_builder=_build_items_result,
        handler=lambda client, params: _call_project_method(client, "collections", "list", params),
        description="List collections for a project.",
    ),
    "project_collections_iter": ToolSpec(
        method_name="project.collections.iter",
        input_model=ProjectParams,
        output_model=ItemsResult,
        output_builder=_build_items_result,
        handler=lambda client, params: _call_project_method(client, "collections", "iter", params),
        description="Iterate collections for a project.",
    ),
    "project_collections_get": ToolSpec(
        method_name="project.collections.get",
        input_model=CollectionsGetParams,
        output_model=ResultWrapper,
        output_builder=_build_result_wrapper,
        handler=lambda client, params: _call_project_method(client, "collections", "get", params),
        description="Fetch a collection by type and name.",
    ),
    "project_collections_get_store": ToolSpec(
        method_name="project.collections.get_store",
        input_model=CollectionsNameParams,
        output_model=ResultWrapper,
        output_builder=_build_result_wrapper,
        handler=lambda client, params: _call_project_method(
            client, "collections", "get_store", params
        ),
        description="Fetch a collection store by name.",
    ),
    "project_collections_get_cached_store": ToolSpec(
        method_name="project.collections.get_cached_store",
        input_model=CollectionsNameParams,
        output_model=ResultWrapper,
        output_builder=_build_result_wrapper,
        handler=lambda client, params: _call_project_method(
            client, "collections", "get_cached_store", params
        ),
        description="Fetch a cached collection store by name.",
    ),
    "project_collections_get_versioned_store": ToolSpec(
        method_name="project.collections.get_versioned_store",
        input_model=CollectionsNameParams,
        output_model=ResultWrapper,
        output_builder=_build_result_wrapper,
        handler=lambda client, params: _call_project_method(
            client, "collections", "get_versioned_store", params
        ),
        description="Fetch a versioned collection store by name.",
    ),
    "project_collections_get_versioned_cached_store": ToolSpec(
        method_name="project.collections.get_versioned_cached_store",
        input_model=CollectionsNameParams,
        output_model=ResultWrapper,
        output_builder=_build_result_wrapper,
        handler=lambda client, params: _call_project_method(
            client, "collections", "get_versioned_cached_store", params
        ),
        description="Fetch a versioned cached collection store by name.",
    ),
    "project_frontiers_list": ToolSpec(
        method_name="project.frontiers.list",
        input_model=ProjectParams,
        output_model=ItemsResult,
        output_builder=_build_items_result,
        handler=lambda client, params: _call_project_method(client, "frontiers", "list", params),
        description="List frontiers for a project.",
    ),
    "project_frontiers_iter": ToolSpec(
        method_name="project.frontiers.iter",
        input_model=ProjectParams,
        output_model=ItemsResult,
        output_builder=_build_items_result,
        handler=lambda client, params: _call_project_method(client, "frontiers", "iter", params),
        description="Iterate frontiers for a project.",
    ),
    "project_frontiers_get": ToolSpec(
        method_name="project.frontiers.get",
        input_model=FrontiersNameParams,
        output_model=ResultWrapper,
        output_builder=_build_result_wrapper,
        handler=lambda client, params: _call_project_method(client, "frontiers", "get", params),
        description="Fetch a frontier by name.",
    ),
    "project_frontiers_flush": ToolSpec(
        method_name="project.frontiers.flush",
        input_model=ProjectParams,
        output_model=ResultWrapper,
        output_builder=_build_result_wrapper,
        handler=lambda client, params: _call_project_method(client, "frontiers", "flush", params),
        description="Flush a project's frontiers.",
    ),
    "project_frontiers_close": ToolSpec(
        method_name="project.frontiers.close",
        input_model=ProjectParams,
        output_model=ResultWrapper,
        output_builder=_build_result_wrapper,
        handler=lambda client, params: _call_project_method(client, "frontiers", "close", params),
        description="Close a project's frontiers.",
    ),
    "project_settings_list": ToolSpec(
        method_name="project.settings.list",
        input_model=SettingsListParams,
        output_model=ItemsResult,
        output_builder=_build_items_result,
        handler=lambda client, params: _call_project_method(client, "settings", "list", params),
        description="List project settings.",
    ),
    "project_settings_iter": ToolSpec(
        method_name="project.settings.iter",
        input_model=ProjectParams,
        output_model=ItemsResult,
        output_builder=_build_items_result,
        handler=lambda client, params: _call_project_method(client, "settings", "iter", params),
        description="Iterate project settings.",
    ),
    "project_settings_get": ToolSpec(
        method_name="project.settings.get",
        input_model=SettingsKeyParams,
        output_model=ResultWrapper,
        output_builder=_build_result_wrapper,
        handler=lambda client, params: _call_project_method(client, "settings", "get", params),
        description="Get a project setting by key.",
    ),
    "project_settings_set": ToolSpec(
        method_name="project.settings.set",
        input_model=SettingsSetParams,
        output_model=ResultWrapper,
        output_builder=_build_result_wrapper,
        handler=lambda client, params: _call_project_method(client, "settings", "set", params),
        description="Set a project setting.",
    ),
    "project_settings_update": ToolSpec(
        method_name="project.settings.update",
        input_model=SettingsUpdateParams,
        output_model=ResultWrapper,
        output_builder=_build_result_wrapper,
        handler=lambda client, params: _call_project_method(client, "settings", "update", params),
        description="Update project settings.",
    ),
    "project_settings_delete": ToolSpec(
        method_name="project.settings.delete",
        input_model=SettingsKeyParams,
        output_model=ResultWrapper,
        output_builder=_build_result_wrapper,
        handler=lambda client, params: _call_project_method(client, "settings", "delete", params),
        description="Delete a project setting.",
    ),
}


def _find_parent(start: Path, predicate: Callable[[Path], bool]) -> Path | None:
    for parent in (start, *start.parents):
        if predicate(parent):
            return parent
    return None


def _resolve_config_path() -> Path:
    search_root = Path.cwd()
    direct_path = search_root / "scrapinghub-mcp.toml"
    if direct_path.is_file():
        return direct_path

    package_root = _find_parent(search_root, lambda root: (root / "pyproject.toml").is_file())
    if package_root is not None:
        config_path = package_root / "scrapinghub-mcp.toml"
        if config_path.is_file():
            return config_path

    repo_root = _find_parent(search_root, lambda root: (root / ".git").is_dir())
    if repo_root is not None:
        config_path = repo_root / "scrapinghub-mcp.toml"
        if config_path.is_file():
            return config_path

    raise RuntimeError(f"Missing scrapinghub-mcp.toml. See {DOCS_URL} for setup.")


def _load_auth_config(config_path: Path) -> tuple[str | None, str | None]:
    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    auth = raw.get("auth")
    if not isinstance(auth, dict):
        return None, None
    api_key = auth.get("api_key")
    env_file = auth.get("env_file")
    api_key_value = api_key.strip() if isinstance(api_key, str) else None
    env_file_value = env_file.strip() if isinstance(env_file, str) else None
    return (api_key_value or None, env_file_value or None)


def _load_allowlist_content() -> tuple[str, str]:
    repo_root = _find_parent(Path.cwd(), lambda root: (root / ".git").is_dir())
    if repo_root is not None:
        override_path = repo_root / ALLOWLIST_FILENAME
        if override_path.is_file():
            return override_path.read_text(encoding="utf-8"), str(override_path)

    try:
        resource = resources.files("scrapinghub_mcp").joinpath(ALLOWLIST_FILENAME)
        return resource.read_text(encoding="utf-8"), f"package:{resource}"
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing {ALLOWLIST_FILENAME}. See {DOCS_URL} for setup.") from exc


def _load_allowlist_schema() -> dict[str, object]:
    global _ALLOWLIST_SCHEMA
    if _ALLOWLIST_SCHEMA is not None:
        return _ALLOWLIST_SCHEMA
    try:
        resource = resources.files("scrapinghub_mcp").joinpath(ALLOWLIST_SCHEMA_FILENAME)
        content = resource.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing {ALLOWLIST_SCHEMA_FILENAME}.") from exc
    _ALLOWLIST_SCHEMA = json.loads(content)
    return _ALLOWLIST_SCHEMA


def _parse_allowlist(content: str) -> set[str]:
    try:
        payload = yaml.safe_load(content) or {}
    except yaml.YAMLError as exc:
        raise RuntimeError(f"Failed to parse {ALLOWLIST_FILENAME}.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{ALLOWLIST_FILENAME} must define a mapping.")
    try:
        schema = _load_allowlist_schema()
        jsonschema.validate(payload, schema)
    except jsonschema.ValidationError as exc:
        raise RuntimeError(f"{ALLOWLIST_FILENAME} is invalid: {exc.message}") from exc

    operations = payload.get("non_mutating") or []
    return set(operations)


def _load_safety_config() -> tuple[set[str], set[str], str | None]:
    try:
        config_path = _resolve_config_path()
    except RuntimeError:
        return set(), set(), None

    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    safety = raw.get("safety")
    if safety is None:
        return set(), set(), str(config_path)
    if not isinstance(safety, dict):
        raise RuntimeError("safety section in scrapinghub-mcp.toml must be a table.")

    extra = safety.get("extra_non_mutating")
    if extra is None:
        extra_items: set[str] = set()
    else:
        if not isinstance(extra, list):
            raise RuntimeError("safety.extra_non_mutating must be a list of strings.")
        extra_values = [item for item in extra if isinstance(item, str) and item.strip()]
        if len(extra_values) != len(extra):
            raise RuntimeError("safety.extra_non_mutating must contain only strings.")
        extra_items = set(extra_values)

    block = safety.get("block_non_mutating")
    if block is None:
        block_items: set[str] = set()
    else:
        if not isinstance(block, list):
            raise RuntimeError("safety.block_non_mutating must be a list of strings.")
        block_values = [item for item in block if isinstance(item, str) and item.strip()]
        if len(block_values) != len(block):
            raise RuntimeError("safety.block_non_mutating must contain only strings.")
        block_items = set(block_values)

    return extra_items, block_items, str(config_path)


def load_non_mutating_operations() -> set[str]:
    content, source = _load_allowlist_content()
    operations = _parse_allowlist(content)
    overrides, blocklist, config_path = _load_safety_config()
    merged = (operations | overrides) - blocklist
    logger.info(
        "allowlist.loaded",
        source=source,
        count=len(operations),
        override_count=len(overrides),
        block_count=len(blocklist),
        merged_count=len(merged),
        config_path=config_path,
    )
    return merged


def resolve_api_key() -> str:
    print(f"scrapinghub-mcp: using working directory {Path.cwd()}", file=sys.stderr)
    try:
        config_path = _resolve_config_path()
    except RuntimeError:
        api_key = os.environ.get(API_KEY_ENV)
        if api_key:
            return api_key
        raise RuntimeError(
            f"Missing scrapinghub-mcp.toml and {API_KEY_ENV}. "
            f"Create scrapinghub-mcp.toml or set {API_KEY_ENV}. See {DOCS_URL} for setup."
        ) from None

    api_key, env_file = _load_auth_config(config_path)

    if env_file:
        env_path = (config_path.parent / env_file).resolve()
        logger.info("auth.env_file.load", path=str(env_path))
        load_dotenv(env_path)

    if api_key:
        return api_key

    logger.info("auth.api_key.fallback", source="env")
    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        raise RuntimeError(
            f"Missing API key in scrapinghub-mcp.toml and {API_KEY_ENV}. "
            f"Set auth.api_key or {API_KEY_ENV}. See {DOCS_URL} for setup."
        )
    return api_key


def register_scrapinghub_tools(
    mcp: MCPType,
    client: Any,
    *,
    allow_mutate: bool,
    non_mutating_operations: set[str],
) -> None:
    def auth_error_message(status_code: int | None) -> str:
        detail = f"HTTP {status_code}" if status_code is not None else "an auth error"
        return (
            f"Authentication failed ({detail}). "
            f"Check {API_KEY_ENV} or auth.api_key in scrapinghub-mcp.toml."
        )

    def auth_error_status(exc: Exception) -> int | None:
        if isinstance(exc, HTTPError):
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)
            if status_code in {401, 403}:
                return status_code
        return None

    def make_tool_wrapper(
        handler: Callable[[Any, BaseModel], Any],
        tool_name: str,
        method_name: str,
        input_model: type[BaseModel],
        output_builder: Callable[[Any], BaseModel],
        description: str,
    ) -> Callable[..., Any]:
        def tool_wrapper(params: BaseModel | None = None) -> BaseModel:
            try:
                if params is None:
                    raw = {}
                elif isinstance(params, BaseModel):
                    raw = params.model_dump()
                elif isinstance(params, dict):
                    raw = params
                else:
                    raise TypeError("Tool params must be a JSON object.")
                validated = input_model.model_validate(raw)
                result = handler(client, validated)
            except Exception as exc:
                status_code = auth_error_status(exc)
                if status_code is not None:
                    logger.warning(
                        "tool.auth_failed",
                        tool=tool_name,
                        method=method_name,
                        status_code=status_code,
                    )
                    raise RuntimeError(auth_error_message(status_code)) from exc
                logger.exception("tool.failed", tool=tool_name, method=method_name)
                raise RuntimeError(f"Scrapinghub tool '{tool_name}' failed.") from exc
            return output_builder(result)

        return tool_wrapper

    for tool_name, spec in TOOL_SPECS.items():
        if spec.method_name not in non_mutating_operations and not allow_mutate:
            logger.info(
                "tool.skipped",
                tool=tool_name,
                method=spec.method_name,
                reason="mutating-default",
            )
            continue
        wrapper = make_tool_wrapper(
            spec.handler,
            tool_name,
            spec.method_name,
            spec.input_model,
            spec.output_builder,
            spec.description,
        )
        wrapper.__annotations__ = {
            "params": spec.input_model | None,
            "return": spec.output_model,
        }
        wrapper.__doc__ = spec.description
        mcp.tool(name=tool_name)(wrapper)
        logger.info("tool.registered", tool=tool_name, method=spec.method_name)


def build_server(*, allow_mutate: bool = False, mcp_cls: type[MCPType] | None = None) -> MCPType:
    api_key = resolve_api_key()
    cls = cast(type[MCPType], FastMCP) if mcp_cls is None else mcp_cls
    mcp = cls("scrapinghub-mcp")
    client = cast(Any, ScrapinghubClient(api_key))
    non_mutating_operations = load_non_mutating_operations()
    register_scrapinghub_tools(
        mcp,
        client,
        allow_mutate=allow_mutate,
        non_mutating_operations=non_mutating_operations,
    )
    return mcp
