"""Edit-aware decomposition into stable shots, boundaries, sequences, and audio events."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from ..evidence.schema import EvaluationUnit, EvidenceManifest
from ..evidence.store import EvidenceStore, sha256_file
from .pp_template.base import Preprocessor

PREPROCESSOR_VERSION = "edit-decomposition-v1"
RUBRIC_BY_UNIT = {
    "shot": ["visual_quality_temporal_stability"],
    "edit_boundary": ["transition_smoothness", "audio_continuity_av_sync"],
    "sequence": ["pacing_narrative_coherence"],
    "audio_event": ["audio_continuity_av_sync"],
}


class VideoDependencyError(RuntimeError):
    pass


@dataclass(frozen=True)
class EditDecompositionConfig:
    boundary_context_seconds: float = 2.0
    reconcile_tolerance_seconds: float = 0.1
    max_sequence_seconds: float = 30.0
    scene_threshold: float = 27.0
    silence_threshold_db: float = -40.0
    minimum_silence_seconds: float = 0.5
    extract_artifacts: bool = True

    def hash(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()[:20]


def video_dependency_status() -> dict[str, Any]:
    return {
        "ffmpeg": shutil.which("ffmpeg"),
        "ffprobe": shutil.which("ffprobe"),
    }


def require_video_binaries() -> dict[str, str]:
    status = video_dependency_status()
    missing = [name for name, path in status.items() if not path]
    if missing:
        raise VideoDependencyError(
            "Edit decomposition requires "
            + ", ".join(missing)
            + ". Install FFmpeg and ensure both ffmpeg and ffprobe are on PATH."
        )
    return {key: str(value) for key, value in status.items()}


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _probe_video(video_path: str, ffprobe: str) -> dict[str, Any]:
    result = _run([
        ffprobe, "-v", "error", "-show_streams", "-show_format",
        "-of", "json", video_path,
    ])
    if result.returncode:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip() or 'unknown error'}")
    payload = json.loads(result.stdout)
    streams = payload.get("streams") or []
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    rate_text = str(video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1")
    try:
        numerator, denominator = rate_text.split("/", 1)
        fps = float(numerator) / float(denominator)
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    duration = float(
        (payload.get("format") or {}).get("duration")
        or video.get("duration")
        or 0.0
    )
    return {
        "duration_seconds": duration,
        "fps": fps,
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "video_codec": video.get("codec_name"),
        "has_audio": audio is not None,
        "audio_codec": audio.get("codec_name") if audio else None,
    }


def _rational_seconds(value: Any) -> Optional[float]:
    if not isinstance(value, dict):
        return None
    raw = value.get("value")
    rate = value.get("rate") or 1
    try:
        return float(raw) / float(rate)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _duration_seconds(node: dict[str, Any]) -> float:
    source_range = node.get("source_range") or {}
    duration = _rational_seconds(source_range.get("duration"))
    if duration is not None:
        return max(0.0, duration)
    raw = (source_range.get("duration") or {}).get("value")
    try:
        return max(0.0, float(raw or 0.0))
    except (TypeError, ValueError):
        return 0.0


def _parse_with_opentimelineio(path: str) -> Optional[dict[str, Any]]:
    try:
        import opentimelineio as otio
        timeline = otio.adapters.read_from_file(path)
    except Exception:  # noqa: BLE001 - JSON fallback supports partial timelines
        return None
    clips: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    boundaries: list[float] = []
    try:
        for track_index, track in enumerate(timeline.tracks):
            kind = str(track.kind or "Unknown")
            for child_index, child in enumerate(track):
                parent_range = track.range_of_child(child)
                output_start = float(parent_range.start_time.to_seconds())
                duration = float(parent_range.duration.to_seconds())
                source_range = getattr(child, "source_range", None)
                source_start = (
                    float(source_range.start_time.to_seconds()) if source_range else None
                )
                record = {
                    "name": getattr(child, "name", None),
                    "track": kind,
                    "track_index": track_index,
                    "child_index": child_index,
                    "output_start": output_start,
                    "output_end": output_start + duration,
                    "duration": duration,
                    "source_start": source_start,
                    "schema": child.schema_name(),
                }
                if isinstance(child, otio.schema.Clip):
                    clips.append(record)
                    if kind.lower() == "video" and output_start > 0:
                        boundaries.append(output_start)
                elif isinstance(child, otio.schema.Gap):
                    gaps.append(record)
                elif isinstance(child, otio.schema.Transition):
                    record.update({
                        "in_offset": float(child.in_offset.to_seconds()),
                        "out_offset": float(child.out_offset.to_seconds()),
                    })
                    transitions.append(record)
                    if kind.lower() == "video":
                        boundaries.append(
                            output_start + float(child.in_offset.to_seconds())
                        )
    except Exception:  # noqa: BLE001 - malformed constructs fall back to raw JSON
        return None
    return {
        "boundaries": sorted(set(round(value, 6) for value in boundaries)),
        "clips": clips,
        "transitions": transitions,
        "gaps": gaps,
        "source": "otio",
        "parser": "opentimelineio",
    }


def parse_otio_timeline(path: str) -> dict[str, Any]:
    """Parse OTIO JSON without requiring the optional OTIO Python package."""
    if not path or not Path(path).is_file():
        return {"boundaries": [], "clips": [], "transitions": [], "gaps": []}
    parsed = _parse_with_opentimelineio(path)
    if parsed is not None:
        return parsed
    try:
        timeline = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {"boundaries": [], "clips": [], "transitions": [], "gaps": []}
    tracks = ((timeline.get("tracks") or {}).get("children") or [])
    clips: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    boundaries: list[float] = []
    for track_index, track in enumerate(tracks):
        if not isinstance(track, dict):
            continue
        kind = str(track.get("kind") or "Unknown")
        cursor = 0.0
        for child_index, child in enumerate(track.get("children") or []):
            if not isinstance(child, dict):
                continue
            schema = str(child.get("OTIO_SCHEMA") or "")
            duration = _duration_seconds(child)
            record = {
                "name": child.get("name"),
                "track": kind,
                "track_index": track_index,
                "child_index": child_index,
                "output_start": cursor,
                "output_end": cursor + duration,
                "duration": duration,
                "source_start": _rational_seconds(
                    ((child.get("source_range") or {}).get("start_time"))
                ),
                "schema": schema,
            }
            if schema.startswith("Clip"):
                clips.append(record)
                if kind.lower() == "video" and cursor > 0:
                    boundaries.append(cursor)
                cursor += duration
            elif schema.startswith("Gap"):
                gaps.append(record)
                cursor += duration
            elif schema.startswith("Transition"):
                in_offset = _rational_seconds(child.get("in_offset")) or 0.0
                out_offset = _rational_seconds(child.get("out_offset")) or 0.0
                record.update({"in_offset": in_offset, "out_offset": out_offset})
                transitions.append(record)
                if kind.lower() == "video":
                    boundaries.append(cursor)
    return {
        "boundaries": sorted(set(round(value, 6) for value in boundaries)),
        "clips": clips,
        "transitions": transitions,
        "gaps": gaps,
        "source": "otio",
    }


def _assembly_boundaries(assembly: dict[str, Any]) -> list[float]:
    clips = [
        clip for clip in (assembly.get("clips") or [])
        if str(clip.get("track") or "").lower() == "video"
    ]
    if not clips:
        return []
    if all(clip.get("output_start") is not None for clip in clips):
        return sorted({
            round(float(clip["output_start"]), 6)
            for clip in clips if float(clip["output_start"]) > 0
        })
    cursor = 0.0
    boundaries: list[float] = []
    for clip in clips:
        if cursor > 0:
            boundaries.append(round(cursor, 6))
        try:
            cursor += max(0.0, float(clip.get("duration") or 0.0))
        except (TypeError, ValueError):
            continue
    return boundaries


def _find_otio_path(sample: dict[str, Any]) -> str:
    output = sample.get("output") or {}
    for candidate in (
        output.get("otio_path"),
        (sample.get("input") or {}).get("otio_path"),
    ):
        if candidate and Path(str(candidate)).is_file():
            return str(candidate)
    for path in (sample.get("input") or {}).get("asset_filepaths") or []:
        if str(path).lower().endswith(".otio") and Path(path).is_file():
            return str(path)
    return ""


def _detect_scenes(video_path: str, threshold: float) -> tuple[list[float], list[str]]:
    warnings: list[str] = []
    try:
        from scenedetect import ContentDetector, SceneManager, open_video
    except ImportError:
        return [], [
            "PySceneDetect is unavailable; rendered boundary detection was skipped. "
            "Install the 'video' optional dependencies."
        ]
    try:
        manager = SceneManager()
        manager.add_detector(ContentDetector(threshold=threshold))
        manager.detect_scenes(video=open_video(video_path))
        scenes = manager.get_scene_list()
        return [round(scene[0].get_seconds(), 6) for scene in scenes[1:]], warnings
    except Exception as error:  # noqa: BLE001 - best-effort fallback is intentional
        return [], [f"Rendered scene detection failed: {type(error).__name__}: {error}"]


def reconcile_boundaries(
    timeline: list[float], rendered: list[float], *, tolerance: float,
) -> list[dict[str, Any]]:
    reconciled: list[dict[str, Any]] = []
    unused = set(range(len(rendered)))
    for timestamp in sorted(timeline):
        candidates = [
            index for index in unused if abs(rendered[index] - timestamp) <= tolerance
        ]
        if candidates:
            index = min(candidates, key=lambda candidate: abs(rendered[candidate] - timestamp))
            unused.remove(index)
            reconciled.append({
                "time": round((timestamp + rendered[index]) / 2.0, 6),
                "provenance": ["timeline", "rendered"],
                "confidence": 1.0,
            })
        else:
            reconciled.append({
                "time": round(timestamp, 6),
                "provenance": ["timeline"],
                "confidence": 0.8,
            })
    for index in sorted(unused):
        reconciled.append({
            "time": round(rendered[index], 6),
            "provenance": ["rendered"],
            "confidence": 0.65,
        })
    return sorted(reconciled, key=lambda boundary: boundary["time"])


_SILENCE_START = re.compile(r"silence_start:\s*([0-9.]+)")
_SILENCE_END = re.compile(r"silence_end:\s*([0-9.]+)")
_BLACK_START = re.compile(r"black_start:\s*([0-9.]+)")
_BLACK_END = re.compile(r"black_end:\s*([0-9.]+)")


def _detect_silence(
    video_path: str, ffmpeg: str, *, threshold_db: float, minimum_seconds: float,
) -> list[tuple[float, float]]:
    result = _run([
        ffmpeg, "-hide_banner", "-nostats", "-i", video_path,
        "-af", f"silencedetect=noise={threshold_db}dB:d={minimum_seconds}",
        "-f", "null", "-",
    ])
    starts = [float(value) for value in _SILENCE_START.findall(result.stderr)]
    ends = [float(value) for value in _SILENCE_END.findall(result.stderr)]
    return [(start, end) for start, end in zip(starts, ends) if end > start]


def _detect_black(video_path: str, ffmpeg: str) -> list[tuple[float, float]]:
    result = _run([
        ffmpeg, "-hide_banner", "-nostats", "-i", video_path,
        "-vf", "blackdetect=d=0.5:pix_th=0.10", "-an", "-f", "null", "-",
    ])
    starts = [float(value) for value in _BLACK_START.findall(result.stderr)]
    ends = [float(value) for value in _BLACK_END.findall(result.stderr)]
    return [(start, end) for start, end in zip(starts, ends) if end > start]


def _unit_id(
    item_id: str, unit_type: str, start: float, end: float, *, ordinal: int,
) -> str:
    identity = f"{item_id}:{unit_type}:{start:.6f}:{end:.6f}:{ordinal}"
    suffix = hashlib.sha256(identity.encode()).hexdigest()[:12]
    return f"{unit_type}-{ordinal:04d}-{suffix}"


def _make_unit(
    item_id: str, unit_type: str, start: float, end: float, ordinal: int, *,
    parent_unit_id: Optional[str] = None, confidence: float = 1.0,
    provenance: Optional[list[str]] = None, measurements: Optional[dict[str, Any]] = None,
) -> EvaluationUnit:
    return EvaluationUnit(
        unit_id=_unit_id(item_id, unit_type, start, end, ordinal=ordinal),
        unit_type=unit_type,  # type: ignore[arg-type]
        start_seconds=round(max(0.0, start), 6),
        end_seconds=round(max(start, end), 6),
        parent_unit_id=parent_unit_id,
        confidence=confidence,
        provenance=list(provenance or []),
        applicable_rubrics=list(RUBRIC_BY_UNIT[unit_type]),
        measurements=dict(measurements or {}),
    )


def _sequence_ranges(
    duration: float, shot_boundaries: list[float], silence: list[tuple[float, float]],
    *, max_seconds: float,
) -> list[tuple[float, float]]:
    split_points = [
        (start + end) / 2.0 for start, end in silence if end - start >= 1.0
    ]
    cursor = 0.0
    points: list[float] = []
    for candidate in sorted(split_points):
        if candidate - cursor >= 3.0:
            points.append(candidate)
            cursor = candidate
    cursor = 0.0
    while duration - cursor > max_seconds:
        target = cursor + max_seconds
        candidates = [value for value in shot_boundaries if cursor + 3.0 < value <= target]
        split = max(candidates) if candidates else target
        points.append(split)
        cursor = split
    ordered = sorted({round(value, 6) for value in points if 0 < value < duration})
    edges = [0.0, *ordered, duration]
    return [(edges[index], edges[index + 1]) for index in range(len(edges) - 1)]


def _extract_clip(
    video_path: str, start: float, end: float, destination: Path, ffmpeg: str,
) -> bool:
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = _run([
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{start:.6f}", "-i", video_path, "-t", f"{max(0.04, end - start):.6f}",
        "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "23", "-c:a", "aac", "-movflags", "+faststart", str(destination),
    ])
    return result.returncode == 0 and destination.is_file()


def _extract_keyframe(
    video_path: str, timestamp: float, destination: Path, ffmpeg: str,
) -> bool:
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = _run([
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{timestamp:.6f}", "-i", video_path, "-frames:v", "1", str(destination),
    ])
    return result.returncode == 0 and destination.is_file()


def _visual_measurements(clip_path: Path) -> dict[str, float]:
    try:
        import cv2
    except ImportError:
        return {}
    capture = cv2.VideoCapture(str(clip_path))
    blur_values: list[float] = []
    luminance: list[float] = []
    frame_count = 0
    while frame_count < 48:
        ok, frame = capture.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur_values.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
        luminance.append(float(gray.mean()))
        frame_count += 1
    capture.release()
    if not blur_values:
        return {}
    mean_blur_variance = sum(blur_values) / len(blur_values)
    luminance_changes = [
        abs(luminance[index] - luminance[index - 1]) / 255.0
        for index in range(1, len(luminance))
    ]
    return {
        "sampled_frame_count": float(frame_count),
        "laplacian_variance": mean_blur_variance,
        "blur_score": 1.0 / (1.0 + mean_blur_variance / 100.0),
        "flicker_score": (
            sum(luminance_changes) / len(luminance_changes) if luminance_changes else 0.0
        ),
    }


def _audio_waveform(
    video_path: str, start: float, end: float, ffmpeg: str,
) -> tuple[list[float], dict[str, float]]:
    result = subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error",
            "-ss", f"{start:.6f}", "-i", video_path,
            "-t", f"{max(0.04, end - start):.6f}", "-vn", "-ac", "1", "-ar", "8000",
            "-f", "s16le", "pipe:1",
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode or not result.stdout:
        return [], {}
    try:
        import numpy as np
    except ImportError:
        return [], {}
    samples = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float64) / 32768.0
    if not len(samples):
        return [], {}
    chunks = np.array_split(samples, min(64, len(samples)))
    waveform = [float(np.sqrt(np.mean(chunk * chunk))) for chunk in chunks if len(chunk)]
    midpoint = max(1, len(samples) // 2)
    pre_rms = float(np.sqrt(np.mean(samples[:midpoint] ** 2)))
    post = samples[midpoint:] if midpoint < len(samples) else samples[:midpoint]
    post_rms = float(np.sqrt(np.mean(post ** 2)))
    discontinuity = abs(post_rms - pre_rms) / max(1e-6, pre_rms + post_rms)
    return waveform, {
        "pre_rms": pre_rms,
        "post_rms": post_rms,
        "energy_discontinuity": discontinuity,
    }


class EditDecompositionPreprocessor(Preprocessor):
    def __init__(
        self, store: EvidenceStore, config: Optional[EditDecompositionConfig] = None,
        *, scene_detector: Optional[Callable[[str, float], tuple[list[float], list[str]]]] = None,
    ) -> None:
        self.store = store
        self.config = config or EditDecompositionConfig()
        self.scene_detector = scene_detector or _detect_scenes

    def cache_key(self, sample: dict[str, Any]) -> tuple[str, str]:
        video_path = str((sample.get("output") or {}).get("output_video_path") or "")
        if not video_path or not Path(video_path).is_file():
            raise FileNotFoundError(f"No rendered video for item {sample.get('item_id', '<unknown>')}")
        video_hash = sha256_file(video_path)
        identity = {
            "item_id": sample.get("item_id"),
            "video_sha256": video_hash,
            "config_hash": self.config.hash(),
            "version": PREPROCESSOR_VERSION,
        }
        cache_key = hashlib.sha256(
            json.dumps(identity, sort_keys=True).encode()
        ).hexdigest()
        return cache_key, video_hash

    def run(self, sample: dict[str, Any], *, force: bool = False) -> EvidenceManifest:
        binaries = require_video_binaries()
        item_id = str(sample.get("item_id") or "")
        video_path = str((sample.get("output") or {}).get("output_video_path") or "")
        cache_key, video_hash = self.cache_key(sample)
        if not force:
            cached = self.store.get_manifest(cache_key)
            if cached is not None:
                return cached

        metadata = _probe_video(video_path, binaries["ffprobe"])
        duration = float(metadata["duration_seconds"])
        if duration <= 0:
            raise RuntimeError(f"Rendered video has no positive duration: {video_path}")
        warnings: list[str] = []
        otio_path = _find_otio_path(sample)
        timeline = parse_otio_timeline(otio_path)
        timeline_boundaries = list(timeline["boundaries"])
        if not timeline_boundaries:
            timeline_boundaries = _assembly_boundaries(
                (sample.get("output") or {}).get("assembly_json") or {}
            )
            if timeline_boundaries:
                timeline["source"] = "assembly_json"
        rendered_boundaries, scene_warnings = self.scene_detector(
            video_path, self.config.scene_threshold
        )
        warnings.extend(scene_warnings)
        tolerance = max(
            self.config.reconcile_tolerance_seconds,
            (2.0 / metadata["fps"]) if metadata["fps"] else 0.1,
        )
        boundaries = [
            boundary for boundary in reconcile_boundaries(
                timeline_boundaries, rendered_boundaries, tolerance=tolerance,
            )
            if 0 < boundary["time"] < duration
        ]
        if not boundaries:
            warnings.append("No edit boundaries detected; using one whole-video shot.")

        silence: list[tuple[float, float]] = []
        black_intervals = _detect_black(video_path, binaries["ffmpeg"])
        if metadata["has_audio"]:
            silence = _detect_silence(
                video_path, binaries["ffmpeg"],
                threshold_db=self.config.silence_threshold_db,
                minimum_seconds=self.config.minimum_silence_seconds,
            )
        else:
            warnings.append("No audio stream; audio rubrics are not applicable.")

        units: list[EvaluationUnit] = []
        shot_edges = [0.0, *[boundary["time"] for boundary in boundaries], duration]
        shots: list[EvaluationUnit] = []
        for index in range(len(shot_edges) - 1):
            unit = _make_unit(
                item_id, "shot", shot_edges[index], shot_edges[index + 1], index,
                provenance=["reconciled_boundaries"],
                measurements={"duration_seconds": shot_edges[index + 1] - shot_edges[index]},
            )
            shots.append(unit)
        units.extend(shots)

        sequences: list[EvaluationUnit] = []
        for index, (start, end) in enumerate(_sequence_ranges(
            duration, [boundary["time"] for boundary in boundaries],
            [*silence, *black_intervals],
            max_seconds=self.config.max_sequence_seconds,
        )):
            sequence = _make_unit(
                item_id, "sequence", start, end, index,
                provenance=["silence_or_max_duration"],
                measurements={"duration_seconds": end - start},
            )
            sequences.append(sequence)
        units.extend(sequences)
        for shot in shots:
            parent = next(
                (sequence for sequence in sequences
                 if sequence.start_seconds <= shot.start_seconds
                 and shot.end_seconds <= sequence.end_seconds + 1e-6),
                None,
            )
            shot.parent_unit_id = parent.unit_id if parent else None

        for index, boundary in enumerate(boundaries):
            time = boundary["time"]
            parent = next(
                (sequence for sequence in sequences
                 if sequence.start_seconds <= time <= sequence.end_seconds),
                None,
            )
            units.append(_make_unit(
                item_id, "edit_boundary",
                max(0.0, time - self.config.boundary_context_seconds),
                min(duration, time + self.config.boundary_context_seconds),
                index, parent_unit_id=parent.unit_id if parent else None,
                confidence=boundary["confidence"], provenance=boundary["provenance"],
                measurements={"boundary_time_seconds": time},
            ))

        if metadata["has_audio"]:
            for index, (start, end) in enumerate(silence):
                units.append(_make_unit(
                    item_id, "audio_event", start, min(end, duration), index,
                    provenance=["ffmpeg_silencedetect"],
                    measurements={"event": "silence", "duration_seconds": end - start},
                ))
            offset = len(silence)
            for index, boundary in enumerate(boundaries):
                time = boundary["time"]
                units.append(_make_unit(
                    item_id, "audio_event", max(0.0, time - 1.0), min(duration, time + 1.0),
                    offset + index, provenance=["edit_boundary_window"],
                    measurements={"event": "boundary_window", "boundary_time_seconds": time},
                ))

        input_data = sample.get("input") or {}
        transcript = input_data.get("a_roll_transcript_text")
        captions = input_data.get("b_roll_captions_excerpt")
        if transcript:
            for sequence in sequences:
                sequence.measurements["transcript_reference"] = str(transcript)
        if captions:
            for sequence in sequences:
                sequence.measurements["caption_reference"] = str(captions)

        if self.config.extract_artifacts:
            store_root = getattr(self.store, "root", None)
            with tempfile.TemporaryDirectory(
                dir=str(store_root) if store_root else None
            ) as tmp:
                staging = Path(tmp)
                for unit in units:
                    clip_path = staging / f"{unit.unit_id}.mp4"
                    if _extract_clip(
                        video_path, unit.start_seconds, unit.end_seconds,
                        clip_path, binaries["ffmpeg"],
                    ):
                        if unit.unit_type in {"shot", "sequence", "edit_boundary"}:
                            unit.measurements.update(_visual_measurements(clip_path))
                        if metadata["has_audio"] and unit.unit_type in {
                            "audio_event", "edit_boundary"
                        }:
                            waveform, audio_measurements = _audio_waveform(
                                video_path, unit.start_seconds, unit.end_seconds,
                                binaries["ffmpeg"],
                            )
                            unit.measurements.update(audio_measurements)
                            if (
                                unit.unit_type == "audio_event"
                                and audio_measurements.get("energy_discontinuity", 0.0) >= 0.5
                            ):
                                unit.measurements["event"] = "abrupt_energy_discontinuity"
                            if waveform:
                                waveform_path = staging / f"{unit.unit_id}.waveform.json"
                                waveform_path.write_text(
                                    json.dumps({
                                        "sample_rate_hz": 8000,
                                        "window_rms": waveform,
                                        "start_seconds": unit.start_seconds,
                                        "end_seconds": unit.end_seconds,
                                    }),
                                    encoding="utf-8",
                                )
                                unit.artifacts.append(self.store.import_artifact(
                                    waveform_path, kind="waveform",
                                    media_type="application/json",
                                    start_seconds=unit.start_seconds,
                                    end_seconds=unit.end_seconds,
                                ))
                        unit.artifacts.append(self.store.import_artifact(
                            clip_path, kind="short_clip", media_type="video/mp4",
                            start_seconds=unit.start_seconds, end_seconds=unit.end_seconds,
                        ))
                    else:
                        warnings.append(f"Clip extraction failed for {unit.unit_id}")
                    if unit.unit_type in {"shot", "sequence"}:
                        frame_path = staging / f"{unit.unit_id}.jpg"
                        midpoint = (unit.start_seconds + unit.end_seconds) / 2.0
                        if _extract_keyframe(
                            video_path, midpoint, frame_path, binaries["ffmpeg"]
                        ):
                            unit.artifacts.append(self.store.import_artifact(
                                frame_path, kind="keyframe", media_type="image/jpeg",
                                start_seconds=midpoint, end_seconds=midpoint,
                            ))

        draft = {
            "item_id": item_id,
            "cache_key": cache_key,
            "source_video_sha256": video_hash,
            "preprocessing_config_hash": self.config.hash(),
            "preprocessor_version": PREPROCESSOR_VERSION,
            "video_metadata": metadata,
            "timeline_provenance": {
                "source": timeline.get("source") or "rendered_only",
                "otio_path": otio_path or None,
                "timeline_boundary_count": len(timeline_boundaries),
                "rendered_boundary_count": len(rendered_boundaries),
                "reconciled_boundary_count": len(boundaries),
                "reconcile_tolerance_seconds": tolerance,
                "clips": timeline.get("clips") or [],
                "transitions": timeline.get("transitions") or [],
                "gaps": timeline.get("gaps") or [],
                "black_intervals": black_intervals,
                "silence_intervals": silence,
            },
            "units": [unit.to_dict() for unit in units],
            "warnings": sorted(set(warnings)),
        }
        evidence_hash = hashlib.sha256(
            json.dumps(draft, sort_keys=True, default=str).encode()
        ).hexdigest()
        manifest = EvidenceManifest(
            item_id=item_id,
            cache_key=cache_key,
            evidence_hash=evidence_hash,
            source_video_path=video_path,
            source_video_sha256=video_hash,
            preprocessing_config_hash=self.config.hash(),
            preprocessor_version=PREPROCESSOR_VERSION,
            video_metadata=metadata,
            timeline_provenance=draft["timeline_provenance"],
            units=units,
            warnings=draft["warnings"],
        )
        self.store.publish_manifest(manifest)
        return manifest
