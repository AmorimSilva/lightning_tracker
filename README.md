# Lightning Tracker

Aplicacao para acompanhar relampagos e eventos GLM, com backend em .NET, scripts Python para renderizacao e tabelas, e frontend em React/Vite.

## Visao geral

O projeto e dividido em tres partes principais:

- Backend HTTP em `webapp/backend`, que expoe a API e chama os scripts Python.
- Frontend em `webapp/frontend`, que consome a API e mostra o mapa, animacao e tabelas.
- Scripts Python em `src/`, que fazem o render PNG, geram tabelas e suportam execucao local/CLI.

## Estrutura principal

- `src/` - pipeline Python de download, processamento, renderizacao e tabelas.
- `webapp/backend/` - API ASP.NET Core (.NET 8).
- `webapp/frontend/` - interface React + Vite.
- `config/` - configuracao principal e lista de tomadores.
- `data/` - dados brutos baixados e caches locais.
- `output/` - saidas geradas, como tabelas CSV.
- `logs/` - logs operacionais.
- `scripts/` - utilitarios de manutencao.

## Requisitos

- Python 3.11 ou superior.
- .NET SDK 8.
- Node.js moderno com npm.
- Credenciais/configuracao AWS validas para o download dos arquivos GLM, quando aplicavel.

## Configuracao

Os arquivos mais importantes de configuracao sao:

- `config/settings.yaml` - parametros de execucao do pipeline Python.
- `config/service_takers.csv` - fallback da lista de tomadores de servico.
- `webapp/backend/appsettings.json` - comandos e caminhos usados pelo backend para chamar o Python.

Pontos relevantes do backend:

- `Python:Command` define o executavel Python usado pelo backend.
- `Python:WorkingDirectory` aponta para a raiz do repositorio ao chamar os modulos Python.
- `Python:SettingsPath` aponta para `config/settings.yaml`.
- `Data:ServiceTakersDbPath` aponta para o SQLite local de tomadores.
- `Data:TablesRootPath` aponta para a raiz dos CSVs de tabela.

## Como rodar o backend

O backend exposto ao frontend roda em `http://localhost:5080` por padrao, conforme `webapp/backend/Properties/launchSettings.json`.

### Rodar localmente

```powershell
Set-Location webapp/backend
dotnet restore
dotnet run
```

Ou, a partir da raiz do repositorio:

```powershell
dotnet run --project webapp/backend
```

### O que o backend faz

- Lista tomadores de servico.
- Renderiza PNGs chamando `python -m src.web_render`.
- Gera tabelas chamando `python -m src.web_tables`.
- Faz cache de frames de renderizacao.

## Como rodar o frontend

O frontend e um app Vite + React que usa proxy para o backend em `/api`.

### Instalar dependencias

```powershell
Set-Location webapp/frontend
npm install
```

### Desenvolvimento

```powershell
npm run dev
```

Por padrao, o Vite encaminha chamadas `/api` para `http://localhost:5080`. Se precisar alterar isso, defina `VITE_API_PROXY_TARGET`.

### Build de producao

```powershell
npm run build
```

### Lint

```powershell
npm run lint
```

## APIs HTTP

Todas as rotas abaixo pertencem ao backend em `webapp/backend`.

### Tomadores

#### `GET /api/takers`

Retorna a lista completa de tomadores como JSON.

Resposta exemplo:

```json
[
  { "id": 1, "name": "Tomador X", "lat": -12.34, "lon": -45.67 }
]
```

#### `GET /api/takers/active`

Retorna o tomador padrao selecionado pela aplicacao.

### Renderizacao de mapa

#### `GET /api/render`

Gera o PNG principal do mapa.

Parametros de query:

- `takerId` (obrigatorio)
- `mode` (obrigatorio, 1 a 4)
- `startLocal` (opcional, `YYYY-MM-DDTHH:MM[:SS]`)
- `endLocal` (opcional, `YYYY-MM-DDTHH:MM[:SS]`)
- `initialLoadHours` (obrigatorio, 0 a 24)
- `background` (0 ou 1)

Modos disponiveis:

1. Flashes com cor por tempo.
2. Flashes por densidade.
3. Eventos espaciais em cinza.
4. Eventos por densidade.

Resposta:

- `image/png`
- Headers `X-*` com metadados do render.

Headers retornados:

- `X-Last-Update-Local`
- `X-Plot-Start-Local`
- `X-Plot-End-Local`
- `X-Flashes-Count`
- `X-Events-Count`
- `X-Mode`
- `X-Dynamic-Start`
- `X-Dynamic-End`
- `X-Initial-Load-Hours`
- `X-Background`

#### `GET /api/render/frame`

Mesma entrada de `/api/render`, com mais um parametro:

- `thumb` (0 ou 1)

Esse endpoint e usado para cache/animacao de frames. Alem dos headers do render, ele tambem retorna:

- `X-Render-Cache`
- `X-Render-Frame-Thumb`

### Tabelas

#### `GET /api/tables/generate`

Gera e salva a tabela CSV do tomador.

Parametros de query:

- `takerId` (obrigatorio)
- `endLocal` (opcional)

Resposta:

- JSON com `csvPath`, `csvRelativePath`, `savedAtLocal`, `endLocal`, `hourLabels`, `radiiLabels` e `values4x24`.

#### `GET /api/tables/latest`

Lista os CSVs mais recentes para um tomador.

Parametros:

- `takerId` (obrigatorio)
- `limit` (opcional, padrao 8)

#### `GET /api/tables/load`

Carrega um CSV salvo e devolve o conteudo em JSON.

Parametros:

- `relativePath` (obrigatorio)

## Scripts Python

### Renderer principal

O renderer principal gera um PNG binario no stdout e escreve metadados `X-*` no stderr.

```powershell
python -m src.web_render --settings config/settings.yaml --name "Tomador" --lat -12.34 --lon -45.67 --mode 1
```

Parametros mais usados:

- `--settings` - caminho do YAML de configuracao.
- `--name` - nome do tomador.
- `--lat` / `--lon` - latitude e longitude.
- `--mode` - modo 1 a 4.
- `--start-local` / `--end-local` - janela local opcional.
- `--initial-load-hours` - otimiza a carga inicial.
- `--background` - ativa o overlay de IR quando disponivel.
- `--thumb` - gera frame menor para cache/animacao.

Exemplo salvando o PNG em arquivo:

```powershell
python -m src.web_render --settings config/settings.yaml --name "Tomador" --lat -12.34 --lon -45.67 --mode 1 > render.png 2> render_headers.txt
```

### Geracao de tabelas

```powershell
python -m src.web_tables --settings config/settings.yaml --name "Tomador" --lat -12.34 --lon -45.67
```

Esse comando salva um CSV no diretorio configurado de tabelas e imprime um JSON resumido no stdout.

### Interface de console

```powershell
python main.py
```

Esse modo abre a selecao interativa de tomador, modo e janela de tempo no terminal.

### Banco local de tomadores

O utilitario abaixo recria o SQLite usado pelo backend a partir do CSV bruto:

```powershell
python scripts/create_service_takers_db.py --csv-path Tomadores_de_servico_latlon.csv --db-path webapp/backend/db/service_takers.sqlite
```

## Docker

O repositório inclui um `Dockerfile` que instala as dependencias Python e executa `python main.py` como comando padrao.

## Verificacao rapida

- `dotnet run --project webapp/backend`
- `npm run dev` em `webapp/frontend`
- `npm run build` em `webapp/frontend`
- `python -m py_compile src/web_render.py`

## Documentacao relacionada

- `docs/TABLES_AND_API.md` - referencia detalhada sobre tabelas e rotas de API.