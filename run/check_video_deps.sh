#!/usr/bin/env bash
set -euo pipefail

missing=()
command -v ffmpeg >/dev/null 2>&1 || missing+=("ffmpeg")
command -v ffprobe >/dev/null 2>&1 || missing+=("ffprobe")

if [ "${#missing[@]}" -gt 0 ]; then
  echo "Missing video tool(s): ${missing[*]}"
  echo "Install FFmpeg (macOS: brew install ffmpeg; Debian/Ubuntu: apt install ffmpeg)"
  echo "and ensure both ffmpeg and ffprobe are available on PATH."
  exit 1
fi

echo "Video preprocessing dependencies are ready:"
ffmpeg -version | head -n 1
ffprobe -version | head -n 1
