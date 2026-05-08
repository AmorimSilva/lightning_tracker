#!/usr/bin/env python3
"""Export ABI IR CH13 as a georeferenced PNG tile for Leaflet ImageOverlay.

Usage:
    python scripts/web_abi_tile.py --settings <path> --utc <ISO8601>
        [--max-dim 1024] [--cmap gray_r]

Output to stdout (binary):
    First line (ASCII): "BOUNDS:<lat_min>,<lon_min>,<lat_max>,<lon_max>\\n"
    Remaining bytes:    PNG image (RGBA, transparent where no data)

The image covers the FULL ABI disk (no geographic clipping).
Reprojection: geostationary fixed-grid → equirectangular lat/lon (scipy griddata nearest).
"""
from __future__ import annotations

import argparse
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

# Prevent any display backend
os.environ.setdefault("MPLBACKEND", "Agg")

# Save the original binary stdout stream so we can write PNG bytes to it.
# Then redirect the global sys.stdout to sys.stderr so print() calls don't corrupt it.
_REAL_STDOUT_BUFFER = sys.stdout.buffer
sys.stdout = sys.stderr

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.background import AbiIrBackgroundProvider
from src.config import load_settings


def _write_stdout(data: bytes) -> None:
    """Write raw bytes directly to the original binary stdout stream."""
    _REAL_STDOUT_BUFFER.write(data)
    _REAL_STDOUT_BUFFER.flush()


# ---------------------------------------------------------------------------
# Reprojection: geostationary fixed-grid → lat/lon
# Algorithm: NOAA ABI fixed-grid projection (PUG-L2, Vol. 5, Section 4.2)
# Same as used in SAT_03_Imagem_projecao_retangular_cinza.ipynb
# ---------------------------------------------------------------------------

def _reproject_full_disk(nc, cmi_data, out_width: int = 2560, out_height: int = 2560):
    """
    Ultra-HD reprojection using inverse mapping and bilinear interpolation.
    """
    import numpy as np
    from scipy.interpolate import RegularGridInterpolator # type: ignore

    # 1. Extraction of projection parameters
    proj_var = nc.variables["goes_imager_projection"]
    h_sat = float(getattr(proj_var, "perspective_point_height"))
    lon0_deg = float(getattr(proj_var, "longitude_of_projection_origin"))
    lon0 = np.radians(lon0_deg)
    r_eq = float(getattr(proj_var, "semi_major_axis"))
    r_pol = float(getattr(proj_var, "semi_minor_axis"))
    H = h_sat + r_eq

    # 2. Get input scan angle axes (radians)
    x_axes = np.asarray(nc.variables["x"][:], dtype=np.float64)
    y_axes = np.asarray(nc.variables["y"][:], dtype=np.float64)
    
    # 3. Create Interpolator for input CMI data
    cmi = np.asarray(cmi_data, dtype=np.float32)
    cmi = np.where(np.isfinite(cmi), cmi, 0)
    interp = RegularGridInterpolator(
        (y_axes, x_axes), 
        cmi, 
        method="linear", 
        bounds_error=False, 
        fill_value=0
    )

    # 4. Define Output Lat/Lon Grid (Full Disk limits)
    # Using fixed bounds for full disk stability
    lat_min, lat_max = -81.3, 81.3
    lon_min, lon_max = lon0_deg - 81.3, lon0_deg + 81.3
    
    lat_grid = np.linspace(lat_max, lat_min, out_height) # N -> S
    lon_grid = np.linspace(lon_min, lon_max, out_width)  # W -> E
    lon_2d, lat_2d = np.meshgrid(lon_grid, lat_grid)
    
    # 5. Inverse Projection: Lat/Lon -> Scan Angles (x, y)
    lat_rad = np.radians(lat_2d)
    lon_rad = np.radians(lon_2d)
    
    # Geocentric latitude
    lat_c = np.arctan((r_pol/r_eq)**2 * np.tan(lat_rad))
    # Geocentric distance to earth surface
    rc = r_pol / np.sqrt(1.0 - (1.0 - (r_pol/r_eq)**2) * np.cos(lat_c)**2)
    
    sx = H - rc * np.cos(lat_c) * np.cos(lon_rad - lon0)
    sy = -rc * np.cos(lat_c) * np.sin(lon_rad - lon0)
    sz = rc * np.sin(lat_c)
    
    # Check visibility
    visible = (sx * (H - sx) - sy**2 - (r_eq/r_pol)**2 * sz**2) > 0
    
    x_out = np.arctan(sy / sx)
    y_out = np.arctan(sz / np.sqrt(sx**2 + sy**2))
    
    # 6. Sample using interpolator
    query_pts = np.stack([y_out.ravel(), x_out.ravel()], axis=1)
    cmi_reproj = interp(query_pts).reshape(out_height, out_width)
    
    # Mask non-visible or NaNs
    cmi_reproj[~visible] = np.nan
    cmi_reproj[cmi_reproj <= 50.0] = np.nan # CMI < 50 is invalid

    return cmi_reproj.astype(np.float32), lat_min, lat_max, lon_min, lon_max


# ---------------------------------------------------------------------------
# Read raw CMI from NetCDF (full disk, subsampled to max_dim)
# ---------------------------------------------------------------------------

def _read_full_disk_cmi(file_path: Path, max_dim: int):
    """Read full-disk CMI from NetCDF and return (Dataset-like context, cmi_array)."""
    import numpy as np
    try:
        from netCDF4 import Dataset  # type: ignore
    except ImportError:
        sys.stderr.write("netCDF4 is required\n")
        return None, None

    # Try relative ASCII path for Windows netCDF4 compat
    open_path = file_path
    try:
        cwd = Path.cwd().resolve()
        rel = file_path.resolve().relative_to(cwd)
        if str(rel).isascii():
            open_path = rel
    except Exception:
        pass

    try:
        with Dataset(str(open_path), mode="r") as ds:
            missing = [v for v in ("CMI", "x", "y", "goes_imager_projection") if v not in ds.variables]
            if missing:
                sys.stderr.write(f"NetCDF missing vars: {missing}\n")
                return None, None

            nx = len(ds.variables["x"])
            ny = len(ds.variables["y"])
            step = max(1, int(max(nx, ny) / max_dim))

            cmi_var = ds.variables["CMI"]
            sub = cmi_var[::step, ::step]
            if hasattr(sub, "filled"):
                sub = sub.filled(np.nan)
            cmi = np.asarray(sub, dtype=np.float32)

            # Return a minimal projection-info dict alongside
            proj = ds.variables["goes_imager_projection"]
            proj_info = {
                "perspective_point_height": float(getattr(proj, "perspective_point_height")),
                "semi_major_axis": float(getattr(proj, "semi_major_axis")),
                "semi_minor_axis": float(getattr(proj, "semi_minor_axis")),
                "longitude_of_projection_origin": float(getattr(proj, "longitude_of_projection_origin")),
            }
            x_full = ds.variables["x"][::step]
            y_full = ds.variables["y"][::step]

            return (proj_info, x_full, y_full), cmi
    except Exception as e:
        sys.stderr.write(f"NetCDF read error: {type(e).__name__}: {e}\n")
        return None, None


# ---------------------------------------------------------------------------
# Colormaps
# ---------------------------------------------------------------------------

def _cmi_to_rgba_png(cmi_data) -> bytes:
    """
    Applies custom meteorological palette:
    - 75C to -30C: Transparent
    - -30C to -85C: gist_ncar colormap
    - Below -85C: Solid White
    """
    import numpy as np
    import matplotlib.pyplot as plt
    from PIL import Image
    import io

    cmi = np.asarray(cmi_data, dtype=np.float32)
    celsius = cmi - 273.15

    # Initialize RGBA (h, w, 4) as transparent zeros
    h, w = celsius.shape
    rgba = np.zeros((h, w, 4), dtype=np.float32)

    # 1. Storm range: -30C to -85C -> gist_ncar
    # Normalize: -30 -> 0.0, -85 -> 1.0
    mask_storm = (celsius <= -30.0) & (celsius >= -85.0)
    if np.any(mask_storm):
        norm_val = (-30.0 - celsius[mask_storm]) / (-30.0 - (-85.0))
        cmap_obj = plt.get_cmap("gist_ncar")
        rgba[mask_storm] = cmap_obj(norm_val)

    # 2. Extreme cold: Below -85C -> White
    mask_extreme = (celsius < -85.0)
    rgba[mask_extreme] = [1.0, 1.0, 1.0, 1.0]

    # 3. Warm range (75C to -30C) stays alpha=0 (already initialized)

    # 4. Handle NaNs
    rgba[~np.isfinite(cmi), 3] = 0

    # Convert to 8-bit PNG
    img_data = (np.clip(rgba, 0, 1) * 255).astype(np.uint8)
    img = Image.fromarray(img_data, mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Export ABI IR full-disk tile PNG (reprojected) to stdout")
    parser.add_argument("--settings", required=True)
    parser.add_argument("--utc", required=True, help="ISO8601 UTC timestamp")
    parser.add_argument("--max-dim", type=int, default=1024, help="Max output dimension (px)")
    parser.add_argument("--cmap", default="gray_r", choices=["gray_r", "ir_enhanced"])
    args = parser.parse_args()

    settings = load_settings(Path(args.settings))

    if not settings.background_enabled:
        sys.stderr.write("ABI background disabled in settings\n")
        return 1

    try:
        dt_utc = datetime.fromisoformat(args.utc.replace("Z", "+00:00"))
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    except Exception as e:
        sys.stderr.write(f"Invalid --utc: {e}\n")
        return 1

    # Use the existing provider only to locate and download the NetCDF file
    provider = AbiIrBackgroundProvider(
        bucket=settings.background_bucket,
        product_prefix=settings.background_product_prefix,
        channel=settings.background_channel,
        cache_dir=settings.background_cache_dir,
        alpha=0.75,
        cmap=args.cmap,
        vmin_k=settings.background_vmin_k,
        vmax_k=settings.background_vmax_k,
        max_dim=args.max_dim,
    )

    diag: dict = {}

    # Find & download the best NetCDF for the requested time
    try:
        found = provider._find_best_key(dt_utc)
    except Exception as e:
        sys.stderr.write(f"S3 list failed: {e}\n")
        return 1

    if found is None:
        sys.stderr.write("No ABI S3 key found for requested time\n")
        return 1

    file_time, key = found
    sys.stderr.write(f"ABI found key: {key} for time {file_time.isoformat()}\n")

    try:
        nc_path = provider._download_key(key)
        sys.stderr.write(f"ABI download success: {nc_path}\n")
    except Exception as e:
        sys.stderr.write(f"ABI download failed: {e}\n")
        return 1

    # ---------------------------------------------------------------------------
    # Open NetCDF and perform reprojection
    # ---------------------------------------------------------------------------
    import numpy as np
    try:
        from netCDF4 import Dataset  # type: ignore
    except ImportError:
        sys.stderr.write("netCDF4 is required\n")
        return 1

    open_path = nc_path
    try:
        rel = nc_path.resolve().relative_to(Path.cwd().resolve())
        if str(rel).isascii():
            open_path = rel
    except Exception:
        pass

    try:
        with Dataset(str(open_path), mode="r") as ds:
            missing = [v for v in ("CMI", "x", "y", "goes_imager_projection") if v not in ds.variables]
            if missing:
                sys.stderr.write(f"NetCDF missing variables: {missing}\n")
                return 1

            nx = len(ds.variables["x"])
            ny = len(ds.variables["y"])

            # Subsample to keep max_dim in scan-angle space (before reprojection)
            # Use a coarser step to keep scipy griddata manageable
            step = max(1, int(max(nx, ny) / args.max_dim))
            sys.stderr.write(f"Disk size: {ny}x{nx}, step={step}\n")

            cmi_var = ds.variables["CMI"]
            sub = cmi_var[::step, ::step]
            if hasattr(sub, "filled"):
                sub = sub.filled(np.nan)
            cmi_sub = np.asarray(sub, dtype=np.float32)

            # Subsample scan-angle axes equally
            x_sub = np.asarray(ds.variables["x"][::step], dtype=np.float64)
            y_sub = np.asarray(ds.variables["y"][::step], dtype=np.float64)

            # Build a minimal Dataset-like object to pass to reprojection
            # We pass ds itself but use subsampled arrays
            proj_var = ds.variables["goes_imager_projection"]

            # ----------------------------------------------------------
            # Reproject: geostationary → lat/lon
            # ----------------------------------------------------------
            sys.stderr.write("Starting reprojection...\n")
            try:
                from scipy.interpolate import griddata  # type: ignore
            except ImportError:
                sys.stderr.write("scipy is required: pip install scipy\n")
                return 1

            H_sat = float(getattr(proj_var, "perspective_point_height"))
            r_eq = float(getattr(proj_var, "semi_major_axis"))
            r_pol = float(getattr(proj_var, "semi_minor_axis"))
            lon0_rad = float(getattr(proj_var, "longitude_of_projection_origin")) * (np.pi / 180.0)
            H = H_sat + r_eq
            e = (r_eq / r_pol) ** 2

            x_2d, y_2d = np.meshgrid(x_sub, y_sub)
            sin_x = np.sin(x_2d); cos_x = np.cos(x_2d)
            sin_y = np.sin(y_2d); cos_y = np.cos(y_2d)

            a_c = sin_x**2 + cos_x**2 * (cos_y**2 + e * sin_y**2)
            b_c = -2.0 * H * cos_x * cos_y
            c_c = H**2 - r_eq**2
            disc = b_c**2 - 4.0 * a_c * c_c

            valid = disc >= 0.0
            r_s = np.full(disc.shape, np.nan, dtype=np.float64)
            r_s[valid] = (-b_c[valid] - np.sqrt(disc[valid])) / (2.0 * a_c[valid])

            s_x = r_s * cos_x * cos_y
            s_y = -r_s * sin_x
            s_z = r_s * cos_x * sin_y

            lat_rad = np.arctan(e * s_z / np.sqrt((H - s_x)**2 + s_y**2))
            lon_rad = lon0_rad - np.arctan(s_y / (H - s_x))

            lat_deg = np.degrees(lat_rad)
            lon_deg = np.degrees(lon_rad)

            # Mask bad CMI values
            cmi_sub[~np.isfinite(cmi_sub)] = np.nan
            cmi_sub[(cmi_sub < 50.0) | (cmi_sub > 550.0)] = np.nan

            # Flatten valid
            flat_lat = lat_deg[valid].ravel()
            flat_lon = lon_deg[valid].ravel()
            flat_cmi = cmi_sub[valid].ravel()

            good = np.isfinite(flat_cmi)
            flat_lat = flat_lat[good]
            flat_lon = flat_lon[good]
            flat_cmi = flat_cmi[good]

            if flat_lat.size == 0:
                sys.stderr.write("No valid data after reprojection\n")
                return 1

            lat_min = float(flat_lat.min())
            lat_max = float(flat_lat.max())
            lon_min = float(flat_lon.min())
            lon_max = float(flat_lon.max())
            sys.stderr.write(f"Disk bounds: lat=[{lat_min:.2f},{lat_max:.2f}] lon=[{lon_min:.2f},{lon_max:.2f}]\n")

            # Subsample source points to keep griddata fast
            max_pts = 1_500_000
            if flat_lat.size > max_pts:
                ss = max(1, int(flat_lat.size / max_pts))
                flat_lat = flat_lat[::ss]
                flat_lon = flat_lon[::ss]
                flat_cmi = flat_cmi[::ss]

            # Output grid: square with max_dim size
            out_w = args.max_dim
            out_h = args.max_dim
            lon_grid = np.linspace(lon_min, lon_max, out_w)
            lat_grid = np.linspace(lat_max, lat_min, out_h)  # N→S
            lon_2d_out, lat_2d_out = np.meshgrid(lon_grid, lat_grid)

            sys.stderr.write(f"griddata: {flat_lat.size} source pts → {out_h}x{out_w} grid...\n")
            cmi_reproj = griddata(
                np.column_stack([flat_lon, flat_lat]),
                flat_cmi,
                (lon_2d_out, lat_2d_out),
                method="nearest",
            )
            sys.stderr.write("Reprojection done.\n")

    except Exception as e:
        sys.stderr.write(f"Reprojection error: {type(e).__name__}: {e}\n")
        return 1

    # ---------------------------------------------------------------------------
    # Render PNG
    # ---------------------------------------------------------------------------
    try:
        png_bytes = _cmi_to_rgba_png(cmi_reproj)
    except Exception as e:
        sys.stderr.write(f"PNG render failed: {e}\n")
        return 1

    # Write bounds + PNG to real stdout (fd 1)
    bounds_line = f"BOUNDS:{lat_min:.4f},{lon_min:.4f},{lat_max:.4f},{lon_max:.4f}\n"
    _write_stdout(bounds_line.encode("ascii") + png_bytes)
    sys.stderr.write(f"Output: {len(png_bytes)} bytes PNG, bounds={bounds_line.strip()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
