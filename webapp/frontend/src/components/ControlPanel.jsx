import './ControlPanel.css'

const ANIM_INTERVALS = [
  { value: 30, label: '30 minutos' },
  { value: 60, label: '1 hora' },
  { value: 120, label: '2 horas' },
  { value: 180, label: '3 horas' },
]

export default function ControlPanel({
  takers,
  takerId,
  onTakerChange,
  animHours,
  onAnimHoursChange,
  startLocal,
  onStartLocalChange,
  endLocal,
  onEndLocalChange,
  backgroundIr,
  onBackgroundIrChange,
  showMap,
  onShowMapChange,
  showRings,
  onShowRingsChange,
}) {
  const selectedTaker = takers.find((t) => String(t.id) === String(takerId))

  return (
    <div className="lt-ctrl">
      {/* Tomador de Serviço */}
      <div className="lt-ctrl__row">
        <label className="lt-ctrl__label">Tomador de Serviço</label>
        <select
          className="lt-ctrl__select"
          value={takerId}
          onChange={(e) => onTakerChange(e.target.value)}
        >
          {takers.map((t) => (
            <option key={t.id} value={String(t.id)}>
              {t.name}
            </option>
          ))}
        </select>
      </div>

      {/* Intervalo de Animação */}
      <div className="lt-ctrl__row">
        <label className="lt-ctrl__label">Intervalo de Animação</label>
        <select
          className="lt-ctrl__select"
          value={animHours * 60}
          onChange={(e) => onAnimHoursChange(Number(e.target.value) / 60)}
        >
          {ANIM_INTERVALS.map((i) => (
            <option key={i.value} value={i.value}>
              {i.label}
            </option>
          ))}
        </select>
      </div>

      {/* Tempo Inicial */}
      <div className="lt-ctrl__row">
        <label className="lt-ctrl__label">Tempo Inicial</label>
        <input
          type="datetime-local"
          className="lt-ctrl__input"
          value={startLocal}
          onChange={(e) => onStartLocalChange(e.target.value)}
        />
      </div>

      {/* Tempo Final */}
      <div className="lt-ctrl__row">
        <label className="lt-ctrl__label">Tempo Final</label>
        {endLocal ? (
          <input
            type="datetime-local"
            className="lt-ctrl__input"
            value={endLocal}
            onChange={(e) => onEndLocalChange(e.target.value)}
          />
        ) : (
          <div className="lt-ctrl__live-badge" onClick={() => onEndLocalChange('')}>
            Ao Vivo
          </div>
        )}
      </div>

      <div className="lt-ctrl__toggles">
        <label className="lt-ctrl__toggle">
          <span>Ativar IR (CH 13)</span>
          <input
            type="checkbox"
            checked={backgroundIr}
            onChange={(e) => onBackgroundIrChange(e.target.checked)}
          />
          <span className={`lt-ctrl__check ${backgroundIr ? 'lt-ctrl__check--on' : ''}`}>
            {backgroundIr ? '✓' : ''}
          </span>
        </label>

        <label className="lt-ctrl__toggle">
          <span>Ativar Mapa</span>
          <input
            type="checkbox"
            checked={showMap}
            onChange={(e) => onShowMapChange(e.target.checked)}
          />
          <span className={`lt-ctrl__check ${showMap ? 'lt-ctrl__check--on' : ''}`}>
            {showMap ? '✓' : ''}
          </span>
        </label>

        <label className="lt-ctrl__toggle">
          <span>Raios de Alcance</span>
          <input
            type="checkbox"
            checked={showRings}
            onChange={(e) => onShowRingsChange(e.target.checked)}
          />
          <span className={`lt-ctrl__check ${showRings ? 'lt-ctrl__check--on' : ''}`}>
            {showRings ? '✓' : ''}
          </span>
        </label>
      </div>
    </div>
  )
}
