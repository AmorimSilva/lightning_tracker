import { useEffect, useMemo, useRef } from 'react'
import { MapContainer, TileLayer, Circle, CircleMarker, Marker, ImageOverlay, useMap } from 'react-leaflet'
import L from 'leaflet'
import { jetColor } from '../utils/haversine'
import './LightningMap.css'

// Black X marker for taker center
const takerIcon = L.divIcon({
  className: 'lt-taker-icon',
  html: `<svg width="28" height="28" viewBox="0 0 28 28"><line x1="6" y1="6" x2="22" y2="22" stroke="black" stroke-width="3.5" stroke-linecap="round"/><line x1="22" y1="6" x2="6" y2="22" stroke="black" stroke-width="3.5" stroke-linecap="round"/></svg>`,
  iconSize: [28, 28],
  iconAnchor: [14, 14],
})

const RING_COLORS = ['#1f77b4', '#2ca02c', '#ff7f0e', '#d62728']
const RING_RADII = [30, 50, 100, 200]

function MapController({ center, zoom }) {
  const map = useMap()
  const prevCenter = useRef(center)
  useEffect(() => {
    if (
      center &&
      (prevCenter.current[0] !== center[0] || prevCenter.current[1] !== center[1])
    ) {
      map.setView(center, zoom, { animate: true })
      prevCenter.current = center
    }
  }, [center, zoom, map])
  return null
}

export default function LightningMap({
  taker,
  allTakers,
  showAllTakers,
  showRings,
  events,
  backgroundIr,
  startLocal,
  endLocal,
  animating,
  animFrameTime,
  onPlay,
  onPause,
  onStepBack,
  onStepForward,
  onDownloadImage,
  onDownloadAnim,
  lastUpdateLocal,
  initialLoadHours,
}) {
  const isSouthAmerica = taker && taker.id === 0
  const center = taker ? [taker.lat, taker.lon] : [-14.0, -52.0]
  const zoom = isSouthAmerica ? 4 : (taker ? 7 : 4)

  // Time range for coloring
  const timeRange = useMemo(() => {
    if (!events || events.length === 0) return { min: 0, max: 1 }
    const times = events.map((e) => new Date(e.eventTime).getTime())
    const min = Math.min(...times)
    const max = Math.max(...times)
    return { min, max: max === min ? max + 1 : max }
  }, [events])

  // Background overlay bounds
  const bgBounds = useMemo(() => {
    if (!taker) return null
    const maxR = 250
    const dLat = maxR / 111.0
    const dLon = maxR / (111.0 * Math.max(0.2, Math.cos((taker.lat * Math.PI) / 180.0)))
    return [
      [taker.lat - dLat, taker.lon - dLon],
      [taker.lat + dLat, taker.lon + dLon],
    ]
  }, [taker])

  const bgUrl = useMemo(() => {
    if (!taker || !backgroundIr) return null
    const qs = new URLSearchParams({ takerId: taker.id, _ts: Date.now() })
    if (endLocal) qs.set('endLocal', endLocal)
    return `/api/background?${qs.toString()}`
  }, [taker, backgroundIr, endLocal])

  // Format metadata
  const now = new Date()
  const effectiveStart = startLocal
    ? new Date(startLocal)
    : new Date(now.getTime() - (initialLoadHours || 4) * 3600000)
  const startLabel = effectiveStart.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
  const endLabel = endLocal
    ? new Date(endLocal).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
    : 'Agora'
  const updateLabel = lastUpdateLocal || now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
  const intervalLabel = initialLoadHours ? `${String(initialLoadHours).padStart(2, '0')}:00` : '04:00'
  const clockLabel = animFrameTime
    ? new Date(animFrameTime).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
    : now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })

  return (
    <div className="lt-map-container">
      <MapContainer
        center={center}
        zoom={zoom}
        className="lt-map"
        zoomControl={false}
        attributionControl={false}
      >
        <MapController center={center} zoom={zoom} />

        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; OpenStreetMap'
        />

        {/* IR background overlay */}
        {bgUrl && bgBounds && (
          <ImageOverlay url={bgUrl} bounds={bgBounds} opacity={0.6} zIndex={1} />
        )}

        {/* Distance rings */}
        {showRings && (showAllTakers && allTakers ? allTakers : (taker ? [taker] : []))
          .filter(t => t.id !== 0)
          .map((t) =>
            RING_RADII.map((r, i) => (
              <Circle
                key={`ring-${t.id}-${r}`}
                center={[t.lat, t.lon]}
                radius={r * 1000}
                pathOptions={{
                  color: RING_COLORS[i],
                  weight: 2,
                  fillOpacity: 0,
                  dashArray: i === 0 ? undefined : '8 4',
                }}
              />
            ))
        )}

        {/* Taker center markers */}
        {showRings && (showAllTakers && allTakers ? allTakers : (taker ? [taker] : []))
          .filter(t => t.id !== 0)
          .map((t) => (
            <Marker key={`marker-${t.id}`} position={[t.lat, t.lon]} icon={takerIcon} />
        ))}

        {/* Lightning events */}
        {events.map((ev) => {
          const t = (new Date(ev.eventTime).getTime() - timeRange.min) / (timeRange.max - timeRange.min)
          return (
            <CircleMarker
              key={ev.id}
              center={[ev.latitude, ev.longitude]}
              radius={5}
              pathOptions={{
                color: 'transparent',
                fillColor: jetColor(t),
                fillOpacity: 0.85,
              }}
            />
          )
        })}
      </MapContainer>

      {/* Metadata overlay (top center) */}
      <div className="lt-map-meta">
        <span>Última atualização: {updateLabel} BRT</span>
        <span>Hora Inicial: {startLabel} BRT</span>
        <span>Hora final: {endLabel === 'Agora' ? endLabel : endLabel + ' BRT'}</span>
        <span>Intervalo: {intervalLabel}</span>
      </div>

      {/* Animation clock (top right) */}
      <div className="lt-map-clock">{clockLabel}</div>

      {/* Animation controls (bottom left) */}
      <div className="lt-map-controls">
        <div className="lt-map-controls__buttons">
          <button onClick={onStepBack} title="Frame anterior" className="lt-map-ctrl-btn">⏮</button>
          {animating ? (
            <button onClick={onPause} title="Pausar" className="lt-map-ctrl-btn">⏸</button>
          ) : (
            <button onClick={onPlay} title="Reproduzir" className="lt-map-ctrl-btn">▶</button>
          )}
          <button onClick={onStepForward} title="Próximo frame" className="lt-map-ctrl-btn">⏭</button>
        </div>
        <div className="lt-map-controls__downloads">
          <button onClick={onDownloadImage} className="lt-map-dl-btn">
            Fazer o Download da Imagem Atual
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3a1 1 0 0 1 1 1v8.59l2.3-2.3a1 1 0 1 1 1.4 1.42l-4 4a1 1 0 0 1-1.4 0l-4-4a1 1 0 1 1 1.4-1.42L11 12.59V4a1 1 0 0 1 1-1Zm-7 14a1 1 0 0 1 1 1v2h12v-2a1 1 0 1 1 2 0v3a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1Z"/></svg>
          </button>
          <button onClick={onDownloadAnim} className="lt-map-dl-btn">
            Fazer o Download da Animação
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3a1 1 0 0 1 1 1v8.59l2.3-2.3a1 1 0 1 1 1.4 1.42l-4 4a1 1 0 0 1-1.4 0l-4-4a1 1 0 1 1 1.4-1.42L11 12.59V4a1 1 0 0 1 1-1Zm-7 14a1 1 0 0 1 1 1v2h12v-2a1 1 0 1 1 2 0v3a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1Z"/></svg>
          </button>
        </div>
      </div>
    </div>
  )
}
