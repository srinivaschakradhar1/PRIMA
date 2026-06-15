# Maintenance Wizard UI

A React + TypeScript (Vite) front-end for the Maintenance Wizard platform. It talks to a
FastAPI backend that defaults to `http://localhost:8080`.

## Prerequisites

- **Node.js** 18+ (Node 20 LTS recommended)
- **npm** 9+ (bundled with Node)
- The **FastAPI backend** running locally if you want live data (default `http://localhost:8080`)

## Getting started

### 1. Install dependencies

```bash
npm install
```

### 2. Configure the backend URL (optional)

The app defaults to `http://localhost:8080`. To point it elsewhere, copy the example
env file and edit the value:

```bash
cp .env.example .env
```

```dotenv
# .env
VITE_API_BASE_URL=http://localhost:8080
```

### 3. Start the dev server

```bash
npm run dev
```

The app starts on **http://localhost:5173**. Requests to `/api/*` are proxied to the
backend configured in `vite.config.ts`.

## Available scripts

| Command           | Description                                              |
| ----------------- | -------------------------------------------------------- |
| `npm run dev`     | Start the Vite dev server with hot reload (port 5173).   |
| `npm run build`   | Type-check and build the production bundle to `dist/`.   |
| `npm run preview` | Serve the production build locally for a final check.    |
| `npm run lint`    | Run ESLint over the project.                             |

## Production build

```bash
npm run build
npm run preview
```

`npm run build` outputs static assets to `dist/`, which can be served by any static host.

## Tech stack

React 19, TypeScript, Vite, MUI, TanStack Query, Zustand, React Router, Plotly.
