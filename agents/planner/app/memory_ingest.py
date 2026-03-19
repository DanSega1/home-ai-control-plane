"""Markdown ingestion job for conversation and PKM memory."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import logging
from pathlib import Path

from engine.interfaces.memory import MemoryDocument, MemoryProvider

from app.config import settings
from app.memory import build_memory_provider

log = logging.getLogger("planner.memory_ingest")


@dataclass
class IngestionStats:
    scanned: int = 0
    ingested: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _load_manifest(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _save_manifest(path: Path, manifest: dict[str, dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True))


def _markdown_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.md") if path.is_file())


def _build_document(path: Path, namespace: str, root: Path) -> MemoryDocument:
    content = path.read_text(encoding="utf-8")
    relative_path = path.relative_to(root).as_posix()
    content_hash = sha256(content.encode("utf-8")).hexdigest()

    return MemoryDocument(
        external_id=f"{namespace}:{relative_path}",
        namespace=namespace,
        content=content,
        metadata={
            "source_path": str(path.resolve()),
            "relative_path": relative_path,
            "content_hash": content_hash,
            "modality": "document",
            "scope": {"source": "home-ai-control-plane"},
        },
        tags=[namespace],
    )


def _roots() -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = [("conversation", Path(settings.memu_conversation_root))]
    if settings.memu_pkm_root:
        roots.append(("pkm", Path(settings.memu_pkm_root)))
    return roots


async def run_ingestion_job(provider: MemoryProvider | None = None) -> IngestionStats:
    if not settings.memu_enabled:
        raise RuntimeError("memU ingestion requires MEMU_ENABLED=true")

    memory_provider = provider or build_memory_provider()
    manifest_path = Path(settings.memu_manifest_path)
    manifest = _load_manifest(manifest_path)
    stats = IngestionStats()

    for namespace, root in _roots():
        if not root.exists():
            log.info("Skipping missing memory root: %s", root)
            continue

        for path in _markdown_files(root):
            stats.scanned += 1
            document = _build_document(path, namespace, root)
            current_hash = str(document.metadata["content_hash"])
            previous = manifest.get(document.external_id)

            if previous and previous.get("content_hash") == current_hash:
                stats.skipped += 1
                continue

            try:
                await memory_provider.memorize([document])
            except Exception as exc:
                stats.failed += 1
                log.error("Failed to ingest %s: %s", path, exc)
                continue

            manifest[document.external_id] = {
                "content_hash": current_hash,
                "namespace": namespace,
                "source_path": str(path.resolve()),
            }
            if previous:
                stats.updated += 1
            else:
                stats.ingested += 1

    _save_manifest(manifest_path, manifest)
    return stats
