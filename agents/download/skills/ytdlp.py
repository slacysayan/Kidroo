"""yt-dlp subprocess skill — `scan` (metadata only) and `download` (mp4).

Requires the `yt-dlp` binary on PATH (see SKILLS.sh). We shell out rather
than importing the module so failures are well-contained and progress can be
streamed line-by-line.
"""
from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel


class VideoMeta(BaseModel):
    source_video_id: str
    title: str
    duration_secs: int | None = None
    url: str
    upload_date: str | None = None
    uploader: str | None = None
    view_count: int | None = None


@dataclass(slots=True)
class DownloadResult:
    file_path: Path
    bytes: int


class YtdlpError(RuntimeError):
    pass


async def scan(url: str) -> list[VideoMeta]:
    """Return a list of VideoMeta for a channel / playlist / single video URL.

    Uses `--dump-json --flat-playlist` so no download happens.
    """
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "--dump-json",
        "--flat-playlist",
        "--no-warnings",
        "--skip-download",
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise YtdlpError(
            f"yt-dlp scan failed ({proc.returncode}): {stderr.decode(errors='replace')[:500]}"
        )
    out: list[VideoMeta] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out.append(
            VideoMeta(
                source_video_id=row.get("id", ""),
                title=row.get("title", ""),
                duration_secs=row.get("duration"),
                url=row.get("url") or row.get("webpage_url") or "",
                upload_date=row.get("upload_date"),
                uploader=row.get("uploader"),
                view_count=row.get("view_count"),
            )
        )
    return out


async def download(
    url: str,
    *,
    staging_dir: Path,
    format_spec: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
) -> AsyncIterator[dict[str, float | str | Path]]:
    """Async generator yielding progress dicts; last yield has `file_path`.

    Yields:
        {"progress": 0.42}                 — mid-download percent (0..1)
        {"stage": "merging"}               — yt-dlp post-processing
        {"file_path": Path, "bytes": int}  — final result
    """
    staging_dir.mkdir(parents=True, exist_ok=True)
    outfile_tpl = str(staging_dir / "%(id)s.%(ext)s")

    cmd = [
        "yt-dlp",
        "-f",
        format_spec,
        "--merge-output-format",
        "mp4",
        "--no-warnings",
        "--newline",
        "--progress",
        "-o",
        outfile_tpl,
        url,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert proc.stdout is not None

    final_path: Path | None = None
    async for raw in proc.stdout:
        line = raw.decode(errors="replace").strip()
        if not line:
            continue

        if line.startswith("[download]") and "%" in line:
            pct = _parse_percent(line)
            if pct is not None:
                yield {"progress": pct}
        elif line.startswith("[Merger]") or line.startswith("[ffmpeg]"):
            yield {"stage": "merging"}
            if "Merging formats into" in line:
                # Capture the final merged filename between double quotes
                try:
                    final_path = Path(line.split('"', 2)[1])
                except IndexError:
                    pass
        elif line.startswith("[download] Destination:"):
            final_path = Path(line.split("Destination:", 1)[1].strip())
        elif "has already been downloaded" in line:
            # e.g. "[download] /tmp/kidroo/abc.mp4 has already been downloaded"
            candidate = line.replace("[download]", "").split(" has already been")[0].strip()
            if candidate:
                final_path = Path(candidate)

    await proc.wait()
    if proc.returncode != 0:
        err = (await proc.stderr.read()).decode(errors="replace") if proc.stderr else ""
        raise YtdlpError(f"yt-dlp download failed ({proc.returncode}): {err[:500]}")

    if final_path is None or not final_path.exists():
        # yt-dlp renames via --merge-output-format; find the latest mp4 in staging
        candidates = sorted(staging_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
        if not candidates:
            raise YtdlpError("yt-dlp reported success but no output file found")
        final_path = candidates[-1]

    yield {"file_path": final_path, "bytes": os.path.getsize(final_path)}


def _parse_percent(line: str) -> float | None:
    """Parse a yt-dlp `[download]   42.0% of ...` line into 0..1."""
    try:
        pct_token = line.split("%", 1)[0].split()[-1]
        return max(0.0, min(1.0, float(pct_token) / 100.0))
    except (IndexError, ValueError):
        return None
