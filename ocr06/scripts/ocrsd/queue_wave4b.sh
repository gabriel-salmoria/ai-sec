#!/usr/bin/env bash
# Starts wave 4b once the wave 4a fetcher has finished (one fetcher at a time).
cd "$(dirname "$0")/../.."
while ps -eo args | grep -v grep | grep -q "jobs_wave4a.json"; do sleep 60; done
exec python3 -u scripts/ocrsd/gen.py scripts/ocrsd/jobs_wave4b.json >> data/ocrsd/wave4b.log 2>&1
