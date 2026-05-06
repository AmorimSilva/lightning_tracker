from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import time
import threading

import matplotlib.pyplot as plt

from src.background import AbiIrBackgroundProvider
from src.config import load_settings
from src.downloader import GLMDownloader
from src.processor import extract_points_from_lcfa
from src.web_render import _to_utc

settings_path = Path('config/settings.yaml')
settings = load_settings(settings_path)

now_local = datetime.now().astimezone()
plot_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
plot_end = now_local
end_utc = min(_to_utc(plot_end), datetime.now(timezone.utc) - timedelta(seconds=settings.aws_availability_lag_sec))
fetch_start_utc = max(end_utc - timedelta(seconds=max(20, settings.aws_interval_seconds)), plot_start.astimezone(timezone.utc))

print('plot_start', plot_start.isoformat(), flush=True)
print('plot_end', plot_end.isoformat(), flush=True)
print('fetch_start_utc', fetch_start_utc.isoformat(), flush=True)
print('end_utc', end_utc.isoformat(), flush=True)

start = time.time()
downloader = GLMDownloader(bucket=settings.aws_bucket, product_prefix=settings.aws_product_prefix, goes_number=19)
print('downloader ready', round(time.time() - start, 2), flush=True)

step = time.time()
dl = downloader.download_range(fetch_start_utc, end_utc, interval_seconds=settings.aws_interval_seconds, dest_root=settings.raw_dir)
print('download_range done', round(time.time() - step, 2), 'count', len(dl.downloaded), 'not_found', dl.not_found, flush=True)

for idx, path in enumerate(dl.downloaded[:5]):
    step = time.time()
    flash = extract_points_from_lcfa(path, kind='flash').df
    print('flash parsed', idx, path.name, len(flash), round(time.time() - step, 2), flush=True)

bg_step = time.time()
provider = AbiIrBackgroundProvider(
    bucket=settings.background_bucket,
    product_prefix=settings.background_product_prefix,
    channel=settings.background_channel,
    cache_dir=settings.background_cache_dir,
    alpha=settings.background_alpha,
    cmap=settings.background_cmap,
    vmin_k=settings.background_vmin_k,
    vmax_k=settings.background_vmax_k,
    max_dim=settings.background_max_dim,
)
fig_tmp, ax_tmp = plt.subplots(figsize=(8, 8), dpi=settings.plot_dpi)
ax_tmp.set_xlim(-50, -40)
ax_tmp.set_ylim(-10, 0)
plt.close(fig_tmp)

state = {'bg': None, 'error': None}

def worker() -> None:
    try:
        state['bg'] = provider.get_background(dt_utc=end_utc, extent=(-50, -40, -10, 0), diag={})
    except Exception as exc:
        state['error'] = exc

thread = threading.Thread(target=worker, daemon=True)
thread.start()
thread.join(timeout=15)
print('background joined', round(time.time() - bg_step, 2), 'alive', thread.is_alive(), 'bg', state['bg'] is not None, 'error', state['error'], flush=True)

print('total', round(time.time() - start, 2), flush=True)
