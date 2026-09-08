import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, writeFileSync, rmSync, unlinkSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { EventEmitter } from 'node:events'
import { readAllowedHosts, domainSettingsPlugin } from './domain-settings.js'

test('saved domains and IPs reload; removal restores the default list', async () => {
  const directory = mkdtempSync(join(tmpdir(), 'marchitect-domains-'))
  const path = join(directory, 'domains.json')
  const httpServer = new EventEmitter()
  try {
    assert.deepEqual(readAllowedHosts(path), [])
    let restarts = 0
    domainSettingsPlugin(path).configureServer({
      httpServer, restart: async () => { restarts++ },
      config: { logger: { error: (message) => assert.fail(message) } },
    })
    const hosts = ['panel.example.com', '192.168.1.10', '2001:db8::1']
    writeFileSync(path, JSON.stringify({ domains: hosts }))
    assert.deepEqual(readAllowedHosts(path), hosts)
    await new Promise((resolve) => setTimeout(resolve, 1200))
    assert.equal(restarts, 1)
    unlinkSync(path)
    await new Promise((resolve) => setTimeout(resolve, 1200))
    assert.equal(restarts, 2)
    assert.deepEqual(readAllowedHosts(path), [])
  } finally {
    httpServer.emit('close')
    rmSync(directory, { recursive: true, force: true })
  }
})
