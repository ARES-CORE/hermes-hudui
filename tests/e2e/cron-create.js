const assert = require('node:assert/strict')
const { chromium } = require('playwright')

// Standalone Playwright smoke test for the Cron create drawer.
// Requires `playwright` to be available to Node, or run it through the Codex
// Playwright skill runner.
const HUD_URL = process.env.HUD_URL || 'http://localhost:5173'

async function main() {
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })

    let createdPayload = null
    let createdJobVisible = false

    await page.addInitScript(() => {
      sessionStorage.setItem('hud-booted', 'true')
      localStorage.setItem('hermes-hudui-lang', 'en')
    })

    await page.route('**/api/dashboard', async () => {
      // Leave the dashboard in its loading state until the test switches tabs.
    })

    await page.route('**/api/cron', async route => {
      const request = route.request()
      if (request.method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            jobs: createdJobVisible ? [{
              id: 'test-cron-job',
              name: createdPayload?.name || 'E2E cron digest',
              prompt: createdPayload?.prompt || '',
              schedule_display: createdPayload?.schedule || '',
              enabled: true,
              state: 'scheduled',
              next_run_at: '2026-04-29T09:00:00-04:00',
              last_run_at: null,
              last_status: null,
              deliver: createdPayload?.deliver || 'local',
              repeat_completed: 0,
              repeat_total: createdPayload?.repeat || null,
              skills: createdPayload?.skills || [],
            }] : [],
          }),
        })
        return
      }

      if (request.method() === 'POST') {
        createdPayload = request.postDataJSON()
        createdJobVisible = true
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ status: 'ok' }),
        })
        return
      }

      await route.fulfill({ status: 405, body: 'method not allowed' })
    })

    await page.goto(HUD_URL, { waitUntil: 'domcontentloaded' })
    await page.getByRole('button', { name: /Cron/i }).click()
    await page.getByRole('button', { name: /Create Job/i }).click()

    await page.locator('input[placeholder="Daily digest"]').fill('E2E cron digest')
    await page.locator('select').first().selectOption('telegram')
    await page.locator('input[placeholder="blank = forever"]').fill('3')

    await page.getByRole('button', { name: /^Cron$/ }).click()
    await page.locator('input[placeholder="0 9 * * *"]').fill('*/15 * * * *')

    await page
      .locator('textarea[placeholder="Self-contained task instruction..."]')
      .fill('Run the E2E cron digest and summarize the result.')

    await page.getByRole('button', { name: '+ Advanced' }).click()
    await page.locator('input[placeholder="llm-wiki, research"]').fill('llm-wiki, research')
    await page.locator('input[placeholder="digest.py"]').fill('digest.py')
    await page.locator('input[placeholder="/home/zerocool/project"]').fill('/tmp/hermes-hudui-e2e')

    await page.getByRole('button', { name: /^Create$/ }).click()
    await page.waitForFunction(() => document.body.textContent.includes('E2E cron digest'))

    assert.deepEqual(createdPayload, {
      schedule: '*/15 * * * *',
      prompt: 'Run the E2E cron digest and summarize the result.',
      name: 'E2E cron digest',
      deliver: 'telegram',
      repeat: 3,
      skills: ['llm-wiki', 'research'],
      script: 'digest.py',
      workdir: '/tmp/hermes-hudui-e2e',
    })

    console.log('Cron create E2E passed')
  } finally {
    await browser.close()
  }
}

main().catch(async error => {
  console.error(error)
  process.exit(1)
})
