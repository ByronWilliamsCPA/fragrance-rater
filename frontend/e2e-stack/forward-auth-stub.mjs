// A stand-in for the production edge (Traefik + Authentik forward-auth + nginx),
// so the browser tests run against the real backend through the same trust
// boundary the real deployment has (ADR-008).
//
// What it reproduces, and why it matters:
//   * The browser never talks to the API directly. Everything goes through here.
//   * Identity comes from a session, not from the request. A session is the
//     `stack_session` cookie holding a username; no cookie means no identity
//     and `/api/*` answers 401, as an unauthenticated user is challenged.
//   * Every `X-Authentik-*` header a client sends is dropped, then the verified
//     username is injected. A client cannot choose its own identity. This is the
//     property nginx.conf and Traefik enforce in production, and the one the
//     trust-boundary spec attacks.
//   * Static files come from the built frontend with the SPA fallback nginx uses.
//
// It is test infrastructure, not a security component: the cookie is a plain
// username. Never run it anywhere an untrusted client can reach it.
//
// Environment:
//   STACK_PORT    port to listen on [8080]
//   BACKEND_URL   the real API server [http://127.0.0.1:8000]
//   STACK_DIST    built frontend directory [./dist]

import { createReadStream, existsSync, statSync } from 'node:fs'
import { createServer, request as httpRequest } from 'node:http'
import { extname, join, normalize, resolve, sep } from 'node:path'

const port = Number(process.env.STACK_PORT ?? 8080)
const backend = new URL(process.env.BACKEND_URL ?? 'http://127.0.0.1:8000')
const dist = resolve(process.env.STACK_DIST ?? './dist')

const types = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
  '.map': 'application/json; charset=utf-8',
}

function sessionUser(req) {
  const match = /(?:^|;\s*)stack_session=([^;]+)/.exec(req.headers.cookie ?? '')
  let value = ''
  try {
    value = match ? decodeURIComponent(match[1]).trim() : ''
  } catch {
    // An undecodable cookie is no session, as at the real edge.
    return ''
  }
  // A username is a short token; anything else is treated as no session.
  return /^[A-Za-z0-9._-]{1,64}$/.test(value) ? value : ''
}

function sendJson(res, status, body) {
  res.writeHead(status, { 'content-type': 'application/json' })
  res.end(JSON.stringify(body))
}

function proxyApi(req, res) {
  const user = sessionUser(req)
  if (!user) {
    sendJson(res, 401, { detail: 'Authentication required' })
    return
  }
  const headers = {}
  for (const [name, value] of Object.entries(req.headers)) {
    // Drop every identity header the client sent, whatever its case.
    if (name.toLowerCase().startsWith('x-authentik-')) continue
    headers[name] = value
  }
  headers['x-authentik-username'] = user
  headers.host = backend.host
  const upstream = httpRequest(
    {
      protocol: backend.protocol,
      hostname: backend.hostname,
      port: backend.port,
      method: req.method,
      path: req.url,
      headers,
    },
    (response) => {
      res.writeHead(response.statusCode ?? 502, response.headers)
      response.pipe(res)
    }
  )
  upstream.on('error', () => sendJson(res, 502, { detail: 'Upstream unavailable' }))
  req.pipe(upstream)
}

function serveStatic(req, res) {
  let pathname
  try {
    pathname = decodeURIComponent(new URL(req.url, 'http://stub').pathname)
  } catch {
    sendJson(res, 400, { detail: 'Bad request' })
    return
  }
  const candidate = normalize(join(dist, pathname))
  const inside = candidate === dist || candidate.startsWith(dist + sep)
  let file = join(dist, 'index.html')
  if (inside && existsSync(candidate) && statSync(candidate).isFile()) file = candidate
  res.writeHead(200, { 'content-type': types[extname(file)] ?? 'application/octet-stream' })
  createReadStream(file).pipe(res)
}

const server = createServer((req, res) => {
  if (req.url === '/__stub/health') {
    sendJson(res, 200, { ok: true })
  } else if (req.url?.startsWith('/api/')) {
    proxyApi(req, res)
  } else {
    serveStatic(req, res)
  }
})

server.listen(port, '127.0.0.1', () => {
  console.log(`forward-auth stub on :${port} -> ${backend.origin}, serving ${dist}`)
})
