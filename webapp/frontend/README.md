# Lightning Tracker Frontend

Interface React + Vite para visualizar os mapas renderizados pelo backend.

## Desenvolvimento

```powershell
npm install
npm run dev
```

O Vite faz proxy de `/api` para `http://localhost:5080` por padrao. Se necessario, ajuste `VITE_API_PROXY_TARGET`.

## Build

```powershell
npm run build
```

## Lint

```powershell
npm run lint
```

## Observacoes

- O frontend nao renderiza o mapa sozinho; ele consome as rotas do backend em `webapp/backend`.
- A documentacao completa do projeto esta no README raiz.
