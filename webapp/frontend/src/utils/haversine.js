/**
 * Calculate the Haversine distance (in km) between two lat/lon points.
 */
export function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371.0
  const dLat = ((lat2 - lat1) * Math.PI) / 180.0
  const dLon = ((lon2 - lon1) * Math.PI) / 180.0
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180.0) *
      Math.cos((lat2 * Math.PI) / 180.0) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2)
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  return R * c
}

/**
 * Map a normalised value [0..1] to a jet-like color for time-based coloring.
 */
export function jetColor(t) {
  const clamped = Math.max(0, Math.min(1, t))
  let r, g, b
  if (clamped < 0.25) {
    r = 0
    g = 4 * clamped
    b = 1
  } else if (clamped < 0.5) {
    r = 0
    g = 1
    b = 1 - 4 * (clamped - 0.25)
  } else if (clamped < 0.75) {
    r = 4 * (clamped - 0.5)
    g = 1
    b = 0
  } else {
    r = 1
    g = 1 - 4 * (clamped - 0.75)
    b = 0
  }
  const toHex = (v) =>
    Math.round(v * 255)
      .toString(16)
      .padStart(2, '0')
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`
}
