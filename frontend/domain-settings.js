import { readFileSync } from 'node:fs'
import { isIP } from 'node:net'

export function readAllowedHosts(path) {
  try {
    const { domains } = JSON.parse(readFileSync(path, 'utf8'))
    if (!Array.isArray(domains) || domains.some((host) => typeof host !== 'string' ||
      (!isIP(host) && (host.length > 253 || !host.includes('.') || host.split('.').some((label) =>
        !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label)))))) {
      throw new Error('Invalid domain settings')
    }
    return domains
  } catch (error) {
    if (error.code !== 'ENOENT') console.error('[marchitect] Could not read domain settings:', error.message)
    return []
  }
}

export function domainSettingsPlugin(path) {
  return {
    name: 'marchitect-domain-settings',
    configureServer(server) {
      // Polling also works with Windows Docker mounts and atomic file replacement.
      let previous = JSON.stringify(readAllowedHosts(path))
      const timer = setInterval(() => {
        const current = JSON.stringify(readAllowedHosts(path))
        if (current !== previous) {
          previous = current
          server.restart().catch((error) => server.config.logger.error(error.message))
        }
      }, 1000)
      timer.unref()
      server.httpServer?.once('close', () => clearInterval(timer))
    },
  }
}
