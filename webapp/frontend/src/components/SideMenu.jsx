import { useState } from 'react'
import './SideMenu.css'

export default function SideMenu({
  open,
  onClose,
  selectedTaker,
  tableData,
  savedTables,
  onGenerateTable,
  onLoadSavedTable,
  onDownloadCsv,
  isGeneratingTable,
  tableStatus,
}) {
  return (
    <>
      {/* Backdrop */}
      {open && <div className="lt-menu-backdrop" onClick={onClose} />}

      <div className={`lt-menu ${open ? 'lt-menu--open' : ''}`}>
        <div className="lt-menu__header">
          <span className="lt-menu__title">MENU</span>
          <button className="lt-menu__close" onClick={onClose}>✕</button>
        </div>

        <div className="lt-menu__section">
          <h3 className="lt-menu__section-title">Download CSV</h3>
          <ul className="lt-menu__list">
            <li>
              <button className="lt-menu__item" onClick={() => onDownloadCsv('yesterday')}>
                Ontem
              </button>
            </li>
            <li>
              <button className="lt-menu__item" onClick={() => onDownloadCsv('last3h')}>
                Últimas 3h
              </button>
            </li>
          </ul>
        </div>

        <div className="lt-menu__section">
          <h3 className="lt-menu__section-title">Tabelas Salvas</h3>
          <button
            className="lt-menu__generate-btn"
            onClick={onGenerateTable}
            disabled={!selectedTaker || isGeneratingTable}
          >
            {isGeneratingTable ? 'Gerando...' : 'Gerar Nova Tabela'}
          </button>

          {tableStatus && <div className="lt-menu__status">{tableStatus}</div>}

          {savedTables.length > 0 ? (
            <ul className="lt-menu__list">
              {savedTables.map((item) => (
                <li key={item.relativePath}>
                  <button
                    className="lt-menu__item"
                    onClick={() => onLoadSavedTable(item.relativePath)}
                  >
                    {item.savedAtLocal || item.lastWriteLocal || item.fileName || item.relativePath}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="lt-menu__empty">Nenhuma tabela salva.</p>
          )}
        </div>
      </div>
    </>
  )
}
