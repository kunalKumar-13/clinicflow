// Captures browser screenshots of the running system for the project evidence.
//
// Run by the pipeline after the stack is up. Every page is the real thing: the
// app served through the Ingress, the live Prometheus Targets page, and the
// Grafana dashboard reading from Prometheus. Nothing is mocked.
//
//   node capture-screenshots.mjs <outDir> <target> [<target> ...]
//
// where each target is one of: app, compose, prometheus, grafana.

import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'

const [outDir = 'screenshots', ...targets] = process.argv.slice(2)
mkdirSync(outDir, { recursive: true })

const GRAFANA_AUTH = 'Basic ' + Buffer.from('admin:clinicflow').toString('base64')

const pages = {
  // The app through the Kubernetes Ingress, by hostname, like a real browser.
  app: {
    url: 'http://clinicflow.local/',
    file: 'app-via-ingress.png',
    ready: async (p) => p.waitForSelector('table tbody tr', { timeout: 60_000 }),
  },
  // The same app from the Docker Compose stack on localhost:3000.
  compose: {
    url: 'http://localhost:3000/',
    file: 'app-docker-compose.png',
    ready: async (p) => p.waitForSelector('table tbody tr', { timeout: 60_000 }),
  },
  // Prometheus scrape targets, filtered to the application.
  prometheus: {
    url: 'http://localhost:9090/targets?search=clinicflow',
    file: 'prometheus-targets.png',
    // The Prometheus UI polls for updates continuously, so the network never
    // goes idle. Treat idle as best-effort and give the table time to render.
    ready: async (p) => {
      await settle(p, 10_000)
      await p.waitForTimeout(6_000)
    },
  },
  // The provisioned ClinicFlow dashboard, in kiosk mode so only the panels show.
  grafana: {
    url: 'http://localhost:3001/d/clinicflow-api/clinicflow-api?orgId=1&from=now-5m&to=now&refresh=10s&kiosk',
    file: 'grafana-dashboard.png',
    headers: { Authorization: GRAFANA_AUTH },
    ready: async (p) => {
      await settle(p, 15_000) // refresh=10s keeps requests going, so best-effort
      await p.waitForTimeout(8_000) // let every panel finish its first query
    },
  },
}

// Wait for the network to go quiet, but do not fail if it never does: pages
// that poll (Prometheus, a refreshing Grafana dashboard) never reach idle.
async function settle(page, timeout) {
  await page.waitForLoadState('networkidle', { timeout }).catch(() => {})
}

const browser = await chromium.launch()
let failures = 0

for (const name of targets) {
  const spec = pages[name]
  if (!spec) {
    console.error(`unknown target "${name}"`)
    failures++
    continue
  }

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    extraHTTPHeaders: spec.headers ?? {},
  })
  const page = await context.newPage()

  try {
    await page.goto(spec.url, { waitUntil: 'domcontentloaded', timeout: 60_000 })
    await spec.ready(page)
    const path = join(outDir, spec.file)
    await page.screenshot({ path, fullPage: false })
    console.log(`captured ${name.padEnd(10)} -> ${path}  (${spec.url})`)
  } catch (err) {
    console.error(`FAILED ${name}: ${err.message}`)
    await page.screenshot({ path: join(outDir, `FAILED-${spec.file}`) }).catch(() => {})
    failures++
  } finally {
    await context.close()
  }
}

await browser.close()
process.exit(failures ? 1 : 0)
