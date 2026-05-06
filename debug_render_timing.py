from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import time

from src.config import load_settings
from src.web_render import RenderParams, render_png

settings_path = Path('config/settings.yaml')
settings = load_settings(settings_path)

params = RenderParams(
    taker_name='Porto Belém',
    lat0=-1.439900541,
    lon0=-48.49492047,
    mode=1,
    start_local=datetime(2026, 5, 5, 0, 0, tzinfo=timezone.utc).astimezone(),
    end_local=datetime(2026, 5, 5, 1, 0, tzinfo=timezone.utc).astimezone(),
    dynamic_start=True,
    dynamic_end=True,
    initial_load_hours=0,
    background=True,
    thumb=True,
)

start = time.time()
print('start')
png, metadata, headers = render_png(settings_path=settings_path, params=params)
print('done', len(png), round(time.time() - start, 2))
print(metadata)
print(headers.get('X-Background-Reason'))
