import { spawn, type ChildProcess } from 'node:child_process'
import { createServer, type Server } from 'node:http'
import { expect, request, test } from '@playwright/test'

/*
 * The stub is the trust boundary these tests lean on, so it is tested too: run
 * in front of an echo server that reports exactly what reached the "backend".
 * Without this, a stub that forgot to strip a header would make the
 * trust-boundary spec pass for the wrong reason (the real backend only reads
 * some of the identity headers, and the stub overwrites the username anyway).
 */
const STUB_PORT = 8091
const ECHO_PORT = 8092
const stubURL = `http://127.0.0.1:${STUB_PORT}`

let echo: Server
let stub: ChildProcess

test.beforeAll(async () => {
  echo = createServer((req, res) => {
    res.writeHead(200, { 'content-type': 'application/json' })
    res.end(JSON.stringify({ method: req.method, url: req.url, headers: req.headers }))
  })
  await new Promise<void>((done) => echo.listen(ECHO_PORT, '127.0.0.1', done))
  stub = spawn('node', ['e2e-stack/forward-auth-stub.mjs'], {
    env: {
      ...process.env,
      STACK_PORT: String(STUB_PORT),
      BACKEND_URL: `http://127.0.0.1:${ECHO_PORT}`,
      STACK_DIST: 'dist',
    },
    stdio: 'ignore',
  })
  const probe = await request.newContext()
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      if ((await probe.get(`${stubURL}/__stub/health`)).ok()) break
    } catch {
      /* not listening yet */
    }
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
  await probe.dispose()
})

test.afterAll(async () => {
  stub.kill()
  await new Promise<void>((done) => echo.close(() => done()))
})

async function client(headers: Record<string, string>) {
  return request.newContext({ baseURL: stubURL, extraHTTPHeaders: headers })
}

test('drops every client-sent identity header, whatever its case, and injects the session user', async () => {
  const api = await client({
    Cookie: 'stack_session=alice',
    'X-Authentik-Username': 'mallory',
    'x-authentik-groups': 'admins',
    'X-AUTHENTIK-UID': 'root',
    'X-Authentik-Email': 'mallory@example.com',
  })

  const seen = (await (await api.get('/api/v1/anything?x=1')).json()).headers as Record<
    string,
    string
  >

  expect(seen['x-authentik-username']).toBe('alice')
  expect(seen['x-authentik-groups']).toBeUndefined()
  expect(seen['x-authentik-uid']).toBeUndefined()
  expect(seen['x-authentik-email']).toBeUndefined()
})

test('passes the method, path and query through unchanged', async () => {
  const api = await client({ Cookie: 'stack_session=alice' })

  const seen = await (
    await api.post('/api/v1/calibration/programs?draft=1', { data: { a: 1 } })
  ).json()

  expect(seen.method).toBe('POST')
  expect(seen.url).toBe('/api/v1/calibration/programs?draft=1')
})

test('an API request with no session, or a malformed one, never reaches the backend', async () => {
  for (const cookie of [
    '',
    'stack_session=',
    'stack_session=bad user!',
    'stack_session=a/b',
    'stack_session=%zz',
  ]) {
    const api = await client(cookie ? { Cookie: cookie } : {})

    const response = await api.get('/api/v1/anything')

    expect(response.status(), cookie).toBe(401)
    expect(await response.text()).not.toContain('headers')
  }
})

test('serves the app shell for a client route, and never a file outside the build', async () => {
  const api = await client({})

  const route = await api.get('/calibration')
  const traversal = await api.get('/..%2f..%2f..%2fetc%2fpasswd')

  expect(route.status()).toBe(200)
  expect(await route.text()).toContain('<div id="root">')
  expect(await traversal.text()).not.toContain('root:')
})
