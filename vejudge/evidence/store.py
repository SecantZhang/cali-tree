"""Evidence store interface and a portable filesystem + SQLite implementation."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .schema import ArtifactRef, EvidenceManifest


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            block = stream.read(chunk_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


class EvidenceStore(ABC):
    @abstractmethod
    def get_manifest(self, cache_key: str) -> Optional[EvidenceManifest]: ...

    @abstractmethod
    def publish_manifest(self, manifest: EvidenceManifest) -> None: ...

    @abstractmethod
    def import_artifact(
        self, source: str | Path, *, kind: str, media_type: Optional[str] = None,
        start_seconds: Optional[float] = None, end_seconds: Optional[float] = None,
    ) -> ArtifactRef: ...


class LocalEvidenceStore(EvidenceStore):
    """Immutable media objects plus normalized, queryable SQLite metadata."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.objects_root = self.root / "objects"
        self.db_path = self.root / "evidence.sqlite3"
        self.objects_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path), timeout=30)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS manifests (
                    cache_key TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL,
                    evidence_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS manifests_item_id ON manifests(item_id);
                CREATE TABLE IF NOT EXISTS units (
                    unit_id TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    unit_type TEXT NOT NULL,
                    parent_unit_id TEXT,
                    start_seconds REAL NOT NULL,
                    end_seconds REAL NOT NULL,
                    confidence REAL NOT NULL,
                    provenance_json TEXT NOT NULL,
                    rubrics_json TEXT NOT NULL,
                    selected_for_judging INTEGER,
                    PRIMARY KEY (cache_key, unit_id),
                    FOREIGN KEY (cache_key) REFERENCES manifests(cache_key) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS units_item_type ON units(item_id, unit_type);
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    cache_key TEXT,
                    unit_id TEXT,
                    kind TEXT NOT NULL,
                    path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    media_type TEXT,
                    start_seconds REAL,
                    end_seconds REAL
                );
                CREATE INDEX IF NOT EXISTS artifacts_unit ON artifacts(cache_key, unit_id);
                CREATE TABLE IF NOT EXISTS measurements (
                    cache_key TEXT NOT NULL,
                    unit_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    PRIMARY KEY (cache_key, unit_id, name)
                );
                CREATE TABLE IF NOT EXISTS provenance (
                    cache_key TEXT NOT NULL,
                    name TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    PRIMARY KEY (cache_key, name)
                );
                """
            )

    def get_manifest(self, cache_key: str) -> Optional[EvidenceManifest]:
        with self._connect() as db:
            row = db.execute(
                "SELECT manifest_json FROM manifests WHERE cache_key=? AND status='ready'",
                (cache_key,),
            ).fetchone()
        if not row:
            return None
        try:
            manifest = EvidenceManifest.from_dict(json.loads(row[0]))
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            return None
        if any(
            not Path(artifact.path).is_file()
            for unit in manifest.units
            for artifact in unit.artifacts
        ):
            return None
        return manifest

    def publish_manifest(self, manifest: EvidenceManifest) -> None:
        payload = json.dumps(manifest.to_dict(), sort_keys=True, ensure_ascii=False)
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                """
                INSERT OR REPLACE INTO manifests
                    (cache_key, item_id, evidence_hash, status, manifest_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    manifest.cache_key, manifest.item_id, manifest.evidence_hash,
                    manifest.status, payload, now,
                ),
            )
            db.execute("DELETE FROM units WHERE cache_key=?", (manifest.cache_key,))
            db.execute("DELETE FROM measurements WHERE cache_key=?", (manifest.cache_key,))
            db.execute("DELETE FROM provenance WHERE cache_key=?", (manifest.cache_key,))
            db.execute("DELETE FROM artifacts WHERE cache_key=?", (manifest.cache_key,))
            for name, value in manifest.timeline_provenance.items():
                db.execute(
                    "INSERT INTO provenance VALUES (?, ?, ?)",
                    (manifest.cache_key, name, json.dumps(value, default=str)),
                )
            for unit in manifest.units:
                db.execute(
                    """
                    INSERT INTO units VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        unit.unit_id, manifest.cache_key, manifest.item_id, unit.unit_type,
                        unit.parent_unit_id, unit.start_seconds, unit.end_seconds,
                        unit.confidence, json.dumps(unit.provenance),
                        json.dumps(unit.applicable_rubrics),
                        None if unit.selected_for_judging is None else int(unit.selected_for_judging),
                    ),
                )
                for name, value in unit.measurements.items():
                    db.execute(
                        "INSERT INTO measurements VALUES (?, ?, ?, ?)",
                        (manifest.cache_key, unit.unit_id, name, json.dumps(value, default=str)),
                    )
                for artifact in unit.artifacts:
                    db.execute(
                        """
                        INSERT OR REPLACE INTO artifacts
                            (artifact_id, cache_key, unit_id, kind, path, sha256, media_type,
                             start_seconds, end_seconds)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            artifact.artifact_id, manifest.cache_key, unit.unit_id,
                            artifact.kind, artifact.path, artifact.sha256, artifact.media_type,
                            artifact.start_seconds, artifact.end_seconds,
                        ),
                    )
            db.commit()

    def import_artifact(
        self, source: str | Path, *, kind: str, media_type: Optional[str] = None,
        start_seconds: Optional[float] = None, end_seconds: Optional[float] = None,
    ) -> ArtifactRef:
        src = Path(source)
        digest = sha256_file(src)
        suffix = src.suffix.lower()
        destination = self.objects_root / digest[:2] / f"{digest}{suffix}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            temporary = destination.with_name(
                f".{destination.name}.{os.getpid()}.{threading.get_ident()}.tmp"
            )
            shutil.copyfile(src, temporary)
            try:
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
        artifact_id = hashlib.sha256(f"{kind}:{digest}".encode()).hexdigest()[:24]
        return ArtifactRef(
            artifact_id=artifact_id,
            kind=kind,
            path=str(destination),
            sha256=digest,
            media_type=media_type,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
        )

    def query_units(
        self, *, item_id: Optional[str] = None, unit_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if item_id:
            clauses.append("item_id=?")
            params.append(item_id)
        if unit_type:
            clauses.append("unit_type=?")
            params.append(unit_type)
        sql = "SELECT unit_id,item_id,unit_type,start_seconds,end_seconds,confidence FROM units"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY item_id,start_seconds,unit_id"
        with self._connect() as db:
            rows = db.execute(sql, params).fetchall()
        return [
            {
                "unit_id": row[0], "item_id": row[1], "unit_type": row[2],
                "start_seconds": row[3], "end_seconds": row[4], "confidence": row[5],
            }
            for row in rows
        ]
