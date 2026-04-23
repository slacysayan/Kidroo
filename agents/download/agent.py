"""Download agent — yt-dlp wrapper for scan + download modes."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from agents.download.skills import ytdlp
from agents.lib.base import BaseAgent
from agents.lib.config import get_settings


class DownloadInput(BaseModel):
    mode: Literal["scan", "download"]
    url: str


class ScanOutput(BaseModel):
    mode: Literal["scan"] = "scan"
    videos: list[ytdlp.VideoMeta]


class DownloadFileOutput(BaseModel):
    mode: Literal["download"] = "download"
    file_path: Path
    bytes: int


DownloadOutput = ScanOutput | DownloadFileOutput


class DownloadAgent(BaseAgent[DownloadInput, DownloadOutput]):
    name = "download"

    async def run(self, inp: DownloadInput) -> DownloadOutput:
        if inp.mode == "scan":
            await self.log.tool_call("yt-dlp.scan", url=inp.url)
            videos = await ytdlp.scan(inp.url)
            await self.log.status("scan complete", n_videos=len(videos))
            return ScanOutput(videos=videos)

        # download mode
        staging = get_settings().download_staging_dir
        await self.log.tool_call("yt-dlp.download", url=inp.url, staging=str(staging))

        final_path: Path | None = None
        final_bytes = 0
        last_logged_pct = -5.0
        async for ev in ytdlp.download(inp.url, staging_dir=staging):
            if "progress" in ev:
                pct = float(ev["progress"]) * 100
                # throttle: only log every 5% step
                if pct - last_logged_pct >= 5 or pct >= 100:
                    await self.log.status("downloading", progress_pct=round(pct, 1))
                    last_logged_pct = pct
            elif "stage" in ev:
                await self.log.status("merging streams")
            elif "file_path" in ev:
                final_path = Path(str(ev["file_path"]))
                final_bytes = int(ev.get("bytes", 0))

        if final_path is None:
            raise RuntimeError("yt-dlp finished without yielding a file_path event")

        await self.log.status(
            "download complete", bytes=final_bytes, path=str(final_path)
        )
        return DownloadFileOutput(file_path=final_path, bytes=final_bytes)
