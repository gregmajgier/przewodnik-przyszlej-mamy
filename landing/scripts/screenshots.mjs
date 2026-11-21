// Regenerates the app screenshots shown on the landing page.
//
// Requires: the app running locally (frontend on :5173, backend on :8000),
// Google Chrome installed, and `cwebp` (brew install webp).
//
//   npm run screenshots
//   APP_URL=... API_URL=... npm run screenshots   # other hosts
//   SKIP_CHAT=1 npm run screenshots               # keep the existing chat shot (no model call)
//
// Logs in as the demo persona (Anna Nowak) through the simulated mObywatel.
// Note: the chat shot sends one real question to the chat model.

import { chromium } from 'playwright-core'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const APP = process.env.APP_URL ?? 'http://localhost:5173'
const API = process.env.API_URL ?? 'http://localhost:8000'
const PERSONA = 'persona-nowak-anna'
const USER_ID = 'user-nowak-anna'
const OUT = fileURLToPath(new URL('../public/screens/', import.meta.url))
const TMP = mkdtempSync(join(tmpdir(), 'mrodzina-shots-'))

// Central content column of the app at 1440 px (used to crop the small card shots).
const COLUMN = { x: 360, width: 720 }
// Step shots: the app's content area (keeps text readable at landing-page size).
const STEP = { x: 340, width: 760, height: 700 }

const login = await fetch(`${API}/api/auth/mobywatel`, {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ persona_id: PERSONA }),
})
if (!login.ok) throw new Error(`Login failed: ${login.status}`)
const { token } = await login.json()

const apps = await (await fetch(`${API}/api/applications`, { headers: { Authorization: `Bearer ${token}` } })).json()
const draft = apps.find((a) => a.status === 'draft')
const accepted = apps.find((a) => a.status === 'accepted')

const browser = await chromium.launch({ channel: 'chrome' })

async function newPage(viewport, deviceScaleFactor = 1) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor, locale: 'pl-PL' })
  await ctx.addInitScript(
    ([t, id]) => {
      localStorage.setItem('token', t)
      localStorage.setItem(`mrodzina:onboarded:${id}`, '1')
    },
    [token, USER_ID],
  )
  return ctx.newPage()
}

mkdirSync(OUT, { recursive: true })

async function save(page, name, clip) {
  await page.waitForTimeout(1200)
  const png = join(TMP, `${name}.png`)
  await page.screenshot({ path: png, clip })
  execFileSync('cwebp', ['-quiet', '-q', '82', png, '-o', join(OUT, `${name}.webp`)])
  console.log('✓', name)
}

async function go(page, path) {
  await page.goto(APP + path, { waitUntil: 'networkidle' })
}

const desk = await newPage({ width: 1440, height: 900 })

// 1. Onboarding analysis: "Sprawdzam, co Wam przysługuje"
await go(desk, '/analiza')
await desk.waitForTimeout(2500)
await save(desk, 'step-1-analiza', { ...STEP, y: 100 })

// 2. Matched benefit with "Dlaczego Wam pasuje"
await go(desk, '/swiadczenia')
await desk.getByText('Zasiłek macierzyński').first().click()
await save(desk, 'step-2-dlaczego', { ...STEP, y: 100 })

// 3. Pre-filled application
if (draft) {
  await go(desk, `/wnioski/${draft.id}`)
  await save(desk, 'step-3-wniosek', { ...STEP, y: 80 })
} else console.warn('! no draft application, skipping step-3-wniosek')

// 4. Calendar
await go(desk, '/kalendarz')
await save(desk, 'step-4-kalendarz', { ...STEP, y: 80 })


// Extras (cropped to the content column)
await go(desk, '/rodzina')
await save(desk, 'extra-rodzina', { ...COLUMN, y: 140, height: 640 })

if (accepted) {
  await go(desk, `/wnioski/${accepted.id}`)
  await desk.mouse.wheel(0, 420)
  await save(desk, 'extra-statusy', { ...COLUMN, y: 140, height: 640 })
} else console.warn('! no accepted application, skipping extra-statusy')

if (!process.env.SKIP_CHAT) {
  await go(desk, '/czat')
  await desk.getByRole('button', { name: /Po porodzie/ }).click()
  // Wait for the answer to finish streaming (the sources list appears at the end).
  await desk.getByText('Źródła', { exact: false }).first().waitFor({ timeout: 90_000 })
  // Frame the question and the start of the answer.
  await desk.locator('.msg-user').last().evaluate((el) => el.scrollIntoView({ block: 'start' }))
  await save(desk, 'extra-czat', { ...COLUMN, y: 60, height: 640 })
}

// Mobile
const phone = await newPage({ width: 390, height: 844 }, 2)
await go(phone, '/')
await phone.waitForTimeout(2500) // let the cards' entrance animation finish
await save(phone, 'mobile-dashboard')

await browser.close()
rmSync(TMP, { recursive: true, force: true })
