import './StatsPanel.css'

const RING_LABELS = ['30km', '50km', '100km', '200km']

export default function StatsPanel({ stats, startLocal, endLocal }) {
  const now = new Date()
  const startLabel = startLocal
    ? new Date(startLocal).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) + ' BRT'
    : now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) + ' BRT'
  const endLabel = endLocal
    ? new Date(endLocal).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) + ' BRT'
    : now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) + ' BRT'

  return (
    <div className="lt-stats">

      {/* Lightning counts */}
      <div className="lt-stats__section-title">Relâmpagos</div>

      <div className="lt-stats__counts-row">
        <div className="lt-stats__count-card">
          <span className="lt-stats__count-value">{stats.total}</span>
          <span className="lt-stats__count-label">Total</span>
        </div>
        <div className="lt-stats__count-card">
          <span className="lt-stats__count-value">{stats.last5min}</span>
          <span className="lt-stats__count-label">Últimos 5 min</span>
        </div>
      </div>

      {/* Per-ring counts */}
      <div className="lt-stats__rings-row">
        {RING_LABELS.map((label, i) => (
          <div key={label} className="lt-stats__ring-card">
            <span className="lt-stats__ring-value">{stats.byRing[i]}</span>
            <span className="lt-stats__ring-label">{label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
