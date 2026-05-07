import argparse
import sys
import os
from pathlib import Path
from datetime import datetime

# Prevent matplotlib from trying to connect to X11/UI
os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib.pyplot as plt

from src.background import AbiIrBackgroundProvider
from src.config import load_settings

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--settings", required=True)
    parser.add_argument("--lon-min", type=float, required=True)
    parser.add_argument("--lon-max", type=float, required=True)
    parser.add_argument("--lat-min", type=float, required=True)
    parser.add_argument("--lat-max", type=float, required=True)
    parser.add_argument("--utc-time", type=str, required=True)
    
    args = parser.parse_args()
    settings = load_settings(Path(args.settings))
    
    if not settings.background_enabled:
        sys.exit(0)

    try:
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
        
        dt_utc = datetime.fromisoformat(args.utc_time)
        extent = (args.lon_min, args.lon_max, args.lat_min, args.lat_max)
        
        diag = {}
        bg = provider.get_background(dt_utc=dt_utc, extent=extent, diag=diag)
        
        if bg is None:
            sys.exit(1)
            
        fig = plt.figure(figsize=(10, 10), dpi=96)
        ax = plt.Axes(fig, [0., 0., 1., 1.])
        ax.set_axis_off()
        fig.add_axes(ax)
        
        from src.web_render import _resolve_background_cmap
        ax.imshow(
            bg.data,
            extent=bg.extent,
            origin=bg.origin,
            cmap=_resolve_background_cmap(bg.cmap),
            alpha=float(bg.alpha),
            vmin=bg.vmin,
            vmax=bg.vmax,
            aspect="auto"
        )
        
        # Output binary PNG to stdout
        sys.stdout.flush()
        fig.savefig(sys.stdout.buffer, format="png", bbox_inches="tight", pad_inches=0, transparent=True)
        
    except Exception as e:
        sys.stderr.write(str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
