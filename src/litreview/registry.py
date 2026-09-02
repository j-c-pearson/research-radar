from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from litreview.models import Registry

ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")


class RegistryValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("\n".join(errors))


def load_registry(path: Path = Path("registry.yaml")) -> Registry:
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except FileNotFoundError as exc:
        raise RegistryValidationError([f"Registry file not found: {path}"]) from exc
    except yaml.YAMLError as exc:
        raise RegistryValidationError([f"Invalid YAML in {path}: {exc}"]) from exc

    try:
        registry = Registry.model_validate(data)
    except ValidationError as exc:
        errors = []
        for err in exc.errors():
            loc = ".".join(str(part) for part in err["loc"])
            errors.append(f"{loc}: {err['msg']}")
        raise RegistryValidationError(errors) from exc

    validate_registry(registry)
    return registry


def validate_registry(registry: Registry) -> None:
    errors: list[str] = []

    category_ids = _check_ids(
        "category", [category.id for category in registry.categories], errors
    )
    source_ids = _check_ids(
        "source", [source.id for source in registry.sources], errors
    )
    topic_ids = _check_ids("topic", [topic.id for topic in registry.topics], errors)
    _check_ids("watch item", [item.id for item in registry.watchlist], errors)

    subcategory_ids_by_category: dict[str, set[str]] = {}
    for category in registry.categories:
        _validate_id("category", category.id, errors)
        subcategory_ids = _check_ids(
            f"subcategory in {category.id}",
            [subcategory.id for subcategory in category.subcategories],
            errors,
        )
        subcategory_ids_by_category[category.id] = subcategory_ids

    for source in registry.sources:
        _validate_id("source", source.id, errors)

    for topic in registry.topics:
        _validate_id("topic", topic.id, errors)
        if topic.category not in category_ids:
            errors.append(
                f"Topic {topic.id} references unknown category: {topic.category}"
            )
        elif topic.subcategory not in subcategory_ids_by_category.get(
            topic.category, set()
        ):
            errors.append(
                f"Topic {topic.id} references unknown subcategory {topic.subcategory} "
                f"for category {topic.category}"
            )
        for source_id in [*topic.sources.include, *topic.sources.exclude]:
            if source_id not in source_ids:
                errors.append(
                    f"Topic {topic.id} references unknown source: {source_id}"
                )
        if not topic.query_terms:
            errors.append(
                f"Topic {topic.id} must define at least one search term or synonym"
            )

    for item in registry.watchlist:
        _validate_id("watch item", item.id, errors)
        if item.type not in {"author", "PI", "pi", "lab", "institution"}:
            errors.append(f"Watch item {item.id} has invalid type: {item.type}")
        if item.orcid and not ORCID_RE.match(item.orcid):
            errors.append(f"Watch item {item.id} has malformed ORCID: {item.orcid}")
        for topic_id in item.related_topics:
            if topic_id not in topic_ids:
                errors.append(
                    f"Watch item {item.id} references unknown topic: {topic_id}"
                )
        for source_id in item.source_ids:
            if source_id not in source_ids:
                errors.append(
                    f"Watch item {item.id} has unknown source ID key: {source_id}"
                )

    label_keys = set(registry.relevance_rules.labels)
    if label_keys != {"high", "medium", "low"}:
        errors.append("relevance_rules.labels must contain exactly: high, medium, low")

    if errors:
        raise RegistryValidationError(errors)


def render_registry_markdown(registry: Registry) -> str:
    lines = [
        f"# {registry.metadata.name}",
        "",
        registry.metadata.description,
        "",
        "## Categories",
        "",
    ]
    categories = {category.id: category for category in registry.categories}
    subcategories = {
        (category.id, subcategory.id): subcategory
        for category in registry.categories
        for subcategory in category.subcategories
    }
    for category in registry.categories:
        lines.extend([f"### {category.name}", "", category.notes, ""])
        for subcategory in category.subcategories:
            lines.append(f"- {subcategory.name}")
        lines.append("")
    lines.extend(["## Topics", ""])
    for topic in registry.topics:
        category = categories[topic.category].name
        subcategory = subcategories[(topic.category, topic.subcategory)].name
        lines.extend(
            [
                f"### {topic.name}",
                "",
                f"- Category: {category}",
                f"- Subcategory: {subcategory}",
                f"- Priority: {topic.priority.value}",
                f"- Search terms: {', '.join(topic.search_terms)}",
                f"- Synonyms: {', '.join(topic.synonyms)}",
                f"- Notes: {topic.notes}",
                "",
            ]
        )
    lines.extend(["## Watchlist", ""])
    for item in registry.watchlist:
        lines.extend(
            [
                f"### {item.name}",
                "",
                f"- Type: {item.type}",
                f"- Affiliation: {item.affiliation}",
                f"- ORCID: {item.orcid}",
                f"- Related topics: {', '.join(item.related_topics)}",
                f"- Notes: {item.notes}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _check_ids(label: str, ids: list[str], errors: list[str]) -> set[str]:
    seen: set[str] = set()
    for item_id in ids:
        _validate_id(label, item_id, errors)
        if item_id in seen:
            errors.append(f"Duplicate {label} ID: {item_id}")
        seen.add(item_id)
    return seen


def _validate_id(label: str, item_id: str, errors: list[str]) -> None:
    if not ID_RE.match(item_id):
        errors.append(f"Invalid {label} ID {item_id!r}; use lowercase snake_case")
