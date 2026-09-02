from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from inspect import Parameter, signature
from typing import Any, Callable, get_type_hints

from pydantic import BaseModel, ConfigDict, Field, create_model

ToolCallable = Callable[..., "BaseModel | dict[str, Any]"]


_ACRONYMS = {
    "id": "ID",
    "ids": "IDs",
    "url": "URL",
    "uri": "URI",
    "html": "HTML",
    "cc": "CC",
    "bcc": "BCC",
    "api": "API",
    "uid": "UID",
    "ical": "iCal",
    "uuid": "UUID",
    "rsvp": "RSVP",
}


def _humanize_parameter_name(name: str) -> str:
    words = []
    for chunk in name.replace("-", "_").split("_"):
        if not chunk:
            continue
        words.append(_ACRONYMS.get(chunk.lower(), chunk.capitalize()))
    return " ".join(words) or name


def _parameter_description(name: str, parameter: Parameter, *, required: bool) -> str:
    description = _humanize_parameter_name(name)
    if required:
        return f"{description}. Required."
    if parameter.default is Parameter.empty:
        return f"{description}. Optional."
    return f"{description}. Optional; defaults to {parameter.default!r}."


def _result_description(service: str, description: str) -> str:
    return f"{service} mock response payload for: {description}"


def _build_docstring(
    *,
    description: str,
    parameter_docs: dict[str, str],
    required_fields: set[str],
    result_description: str,
) -> str:
    lines = [description.strip(), "", "Parameters:"]
    for name, doc in parameter_docs.items():
        requirement = "required" if name in required_fields else "optional"
        lines.append(f"    {name}: {doc} ({requirement})")
    lines.extend(
        [
            "",
            "Returns:",
            f"    {result_description}",
        ]
    )
    return "\n".join(lines)


def _safe_default(value: Any) -> Any:
    try:
        return deepcopy(value)
    except Exception:
        return value


def _pascal_case(name: str) -> str:
    return "".join(part.capitalize() for part in name.lower().split("_"))


def _build_args_model(
    tool_name: str,
    func: ToolCallable,
    *,
    parameter_docs: dict[str, str],
    required_fields: set[str],
) -> type[BaseModel]:
    # Mock tools use ``from __future__ import annotations``, so
    # ``parameter.annotation`` returns string forward refs (e.g. "GmailAttachment | None").
    # ``get_type_hints`` resolves those against the function's own module globals so
    # Pydantic can produce a fully-typed schema natively, no post-hoc patching needed.
    try:
        resolved_hints = get_type_hints(func)
    except Exception:
        resolved_hints = {}
    fields: dict[str, tuple[Any, Any]] = {}
    for name, parameter in signature(func).parameters.items():
        if name in resolved_hints:
            annotation = resolved_hints[name]
        elif parameter.annotation is not Parameter.empty:
            annotation = parameter.annotation
        else:
            annotation = Any
        required = name in required_fields or parameter.default is Parameter.empty
        default = ... if required else _safe_default(parameter.default)
        fields[name] = (
            annotation,
            Field(default=default, description=parameter_docs[name]),
        )

    model = create_model(  # type: ignore[call-overload]
        f"{_pascal_case(tool_name)}Args",
        __base__=BaseModel,
        __config__=ConfigDict(extra="forbid"),
        **fields,
    )
    model.__doc__ = f"Arguments for {tool_name}."
    return model


def _resolve_return_type(func: ToolCallable) -> Any:
    """Pull the tool's declared return type so the result envelope can be typed.

    Falls back to dict[str, Any] for legacy tools that still return raw dicts.
    """
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}
    return hints.get("return", dict[str, Any])


def _build_result_model(
    tool_name: str,
    *,
    result_description: str,
    return_type: Any,
) -> type[BaseModel]:
    model = create_model(  # type: ignore[call-overload]
        f"{_pascal_case(tool_name)}Result",
        __base__=BaseModel,
        __config__=ConfigDict(extra="allow"),
        result=(return_type, Field(description=result_description)),
    )
    model.__doc__ = f"Result envelope for {tool_name}."
    return model


@dataclass(frozen=True)
class ToolSpec:
    name: str
    service: str
    callable: ToolCallable
    description: str
    docstring: str
    args_model: type[BaseModel]
    result_model: type[BaseModel]

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def invoke(self, **kwargs: Any) -> BaseModel:
        validated_args = self.args_model.model_validate(kwargs)
        result = self.callable(**validated_args.model_dump())
        return self.result_model.model_validate({"result": result})


def build_tool_spec(
    *,
    service: str,
    name: str,
    func: ToolCallable,
    description: str,
    required_fields: set[str] | None = None,
) -> ToolSpec:
    required = set(required_fields or set())
    parameter_docs = {
        param_name: _parameter_description(
            param_name,
            parameter,
            required=param_name in required or parameter.default is Parameter.empty,
        )
        for param_name, parameter in signature(func).parameters.items()
    }
    result_description = _result_description(service, description)
    docstring = _build_docstring(
        description=description,
        parameter_docs=parameter_docs,
        required_fields=required,
        result_description=result_description,
    )
    func.__doc__ = docstring
    return ToolSpec(
        name=name,
        service=service,
        callable=func,
        description=description,
        docstring=docstring,
        args_model=_build_args_model(
            name,
            func,
            parameter_docs=parameter_docs,
            required_fields=required,
        ),
        result_model=_build_result_model(
            name,
            result_description=result_description,
            return_type=_resolve_return_type(func),
        ),
    )


@dataclass(frozen=True)
class ToolDefinition:
    """Typed configuration for a single tool registration."""

    name: str
    callable: ToolCallable
    description: str
    required_fields: frozenset[str] = frozenset()


def build_tool_registry(
    *,
    service: str,
    definitions: list[ToolDefinition] | dict[str, dict[str, Any]],
) -> dict[str, ToolSpec]:
    typed_defs = _coerce_definitions(definitions)
    return {
        definition.name: build_tool_spec(
            service=service,
            name=definition.name,
            func=definition.callable,
            description=definition.description,
            required_fields=set(definition.required_fields),
        )
        for definition in typed_defs
    }


def _coerce_definitions(
    definitions: list[ToolDefinition] | dict[str, dict[str, Any]],
) -> list[ToolDefinition]:
    if isinstance(definitions, list):
        return definitions
    return [
        ToolDefinition(
            name=name,
            callable=entry["callable"],
            description=entry["description"],
            required_fields=frozenset(entry.get("required_fields", set())),
        )
        for name, entry in definitions.items()
    ]
