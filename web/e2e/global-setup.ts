import { spawn } from 'node:child_process'
import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(__dirname, '../..')
const PYTHON = path.join(REPO_ROOT, '.venv/bin/python3')

// The frontend's API base URL is baked in at build time (Vite inlines
// import.meta.env.VITE_API_BASE_URL), so the backend MUST run on the exact port that
// was already baked into the build `run/run_e2e_tests.sh` produced — there's no way to
// discover a dynamic port after the fact. One env var, read on both sides, is the
// single source of truth; default matches run_e2e_tests.sh's default.
const BACKEND_URL = new URL(process.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8611')
const BACKEND_PORT = Number(BACKEND_URL.port)

interface FixturePaths {
  data_root: string
  rendered_root: string
  annotations_root: string
  use_cases_path: string
}

function waitForHttp(url: string, timeoutMs = 20000): Promise<void> {
  const start = Date.now()
  return new Promise((resolve, reject) => {
    const check = async () => {
      try {
        const res = await fetch(url)
        if (res.ok) return resolve()
      } catch {
        // not up yet
      }
      if (Date.now() - start > timeoutMs) return reject(new Error(`timed out waiting for ${url}`))
      setTimeout(check, 200)
    }
    check()
  })
}

async function buildFixtureTree(tmpDir: string): Promise<FixturePaths> {
  return new Promise((resolve, reject) => {
    const proc = spawn(PYTHON, [path.join(REPO_ROOT, 'tests/e2e_fixture.py'), tmpDir])
    let out = ''
    proc.stdout.on('data', (d) => (out += d.toString()))
    proc.stderr.on('data', (d) => process.stderr.write(d))
    proc.on('exit', (code) => {
      if (code === 0) resolve(JSON.parse(out.trim()))
      else reject(new Error(`tests/e2e_fixture.py exited with code ${code}`))
    })
  })
}

function startMockGateway(): Promise<{ pid: number; port: number }> {
  return new Promise((resolve, reject) => {
    const proc = spawn(PYTHON, [path.join(REPO_ROOT, 'tests/e2e/mock_gateway.py'), '0'])
    let resolved = false
    proc.stdout.on('data', (d) => {
      if (resolved) return
      const line = d.toString().split('\n')[0]?.trim()
      const port = Number(line)
      if (!Number.isNaN(port) && port > 0) {
        resolved = true
        resolve({ pid: proc.pid!, port })
      }
    })
    proc.on('exit', (code) => {
      if (!resolved) reject(new Error(`mock_gateway.py exited early with code ${code}`))
    })
    setTimeout(() => {
      if (!resolved) reject(new Error('timed out waiting for mock gateway to report its port'))
    }, 10000)
  })
}

export default async function globalSetup(): Promise<void> {
  const tmpDir = mkdtempSync(path.join(tmpdir(), 'vejudge-e2e-'))

  const fixture = await buildFixtureTree(tmpDir)
  const gateway = await startMockGateway()

  const backend = spawn(
    PYTHON,
    ['-m', 'vejudge.interface.server', '--port', String(BACKEND_PORT)],
    {
      cwd: REPO_ROOT,
      env: {
        ...process.env,
        VEJUDGE_DATA_ROOT: fixture.data_root,
        VEJUDGE_RENDERED_ROOT: fixture.rendered_root,
        VEJUDGE_HUMAN_ANNOTATIONS_ROOT: fixture.annotations_root,
        VEJUDGE_USE_CASES_CONFIG: fixture.use_cases_path,
        // Scratch areas — never the real repo's logs/, workflows/, or credentials file.
        VEJUDGE_WORKFLOWS_ROOT: path.join(tmpDir, 'workflows'),
        VEJUDGE_LOGS_ROOT: path.join(tmpDir, 'logs'),
        VEJUDGE_CREDENTIALS_FILE: path.join(tmpDir, 'interface_credentials.json'),
        OPENAI_COMPAT_BASE_URL: `http://127.0.0.1:${gateway.port}`,
        CHAT_GPT_API_KEY: 'sk-e2e-fake',
      },
    },
  )

  await waitForHttp(`${BACKEND_URL.origin}/api/nodes`)

  const stateFile = path.join(tmpDir, 'e2e-state.json')
  writeFileSync(
    stateFile,
    JSON.stringify({ tmpDir, gatewayPid: gateway.pid, backendPid: backend.pid }),
  )
  process.env.E2E_STATE_FILE = stateFile
}
