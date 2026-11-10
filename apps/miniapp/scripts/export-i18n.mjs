// Regenerates src/i18n/*.json from tulporgo_core.i18n (the single source of UI texts).
//   npm run i18n          write the files
//   npm run i18n:check    exit 1 when they are stale
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '..')
const pythonPath = [path.join(root, 'packages', 'core'), path.join(root, 'apps', 'api')].join(path.delimiter)
const res = spawnSync('uv', ['run', 'python', '-m', 'tulporgo_api.export_i18n', ...process.argv.slice(2)], {
  cwd: root,
  stdio: 'inherit',
  env: { ...process.env, PYTHONPATH: pythonPath },
  shell: process.platform === 'win32',
})
process.exit(res.status ?? 1)
