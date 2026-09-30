import { execFileSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { mkdtemp, readFile, readdir, rm, mkdir, copyFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createClient } from '@hey-api/openapi-ts'

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const root = resolve(frontend, '..')
const check = process.argv.includes('--check')
const temporary = await mkdtemp(join(tmpdir(), 'copilot-contracts-'))
const snapshot = join(temporary, 'openapi.json')
const generated = join(temporary, 'generated')
const python = process.env.CONTRACT_PYTHON ?? (existsSync(join(root, '.venv-mcp/bin/python'))
  ? join(root, '.venv-mcp/bin/python') : 'python3')

try {
  execFileSync(python, ['-m', 'research_copilot.app.export_contracts', '--output', snapshot], {
    cwd: root, stdio: ['ignore', 'ignore', 'inherit'],
  })
  await createClient({
    input: snapshot,
    output: generated,
    plugins: ['@hey-api/typescript', {
      name: 'zod', definitions: true, requests: false, responses: false,
      dates: { offset: true },
    }],
  })
  const pairs = [[snapshot, join(frontend, 'contracts/openapi.json')]]
  const files = (await readdir(generated)).sort()
  for (const name of files) pairs.push([join(generated, name), join(frontend, 'src/api/contracts/generated', name)])
  const destination = join(frontend, 'src/api/contracts/generated')
  if (check && existsSync(destination)) {
    const extras = (await readdir(destination)).filter((name) => !files.includes(name))
    if (extras.length) throw new Error(`Obsolete generated files: ${extras.join(', ')}`)
  }
  for (const [source, target] of pairs) {
    if (check) {
      if (!existsSync(target) || !(await readFile(source)).equals(await readFile(target))) {
        throw new Error(`Contract drift: ${target}. Run npm run contracts:generate.`)
      }
    } else {
      await mkdir(dirname(target), { recursive: true })
      await copyFile(source, target)
    }
  }
  console.log(check ? 'Contracts match backend declarations.' : 'Contracts generated.')
} finally {
  await rm(temporary, { recursive: true, force: true })
}
