import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const python = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
function run(command, args, cwd = root) {
  const result = spawnSync(command, args, { cwd, stdio: 'inherit', env: {
    ...process.env,
    // Allow source installs on new Python versions without a C++ toolchain.
    PYYAML_FORCE_LIBYAML: process.env.PYYAML_FORCE_LIBYAML ?? '0',
  } });
  if (result.error || result.status !== 0) {
    console.error(result.error?.message ?? `Setup failed (${result.status}).`);
    process.exit(1);
  }
}
if (!existsSync(python)) run(process.env.PYTHON || 'python', ['-m', 'venv', '.venv']);
run(python, ['-m', 'ensurepip', '--upgrade']);
run(python, ['-m', 'pip', 'install', '-e', 'backend/packages/shared-py[dev,web]',
  '-e', 'backend/services/survey-manager[dev]', '-e', 'backend/services/respondent[dev]',
  '-e', 'backend/services/data-analyzer[dev]', '-e', 'backend/services/worker[dev]',
  '-e', 'backend/services/liana-connector[dev]']);
// npm supplies the CLI path during lifecycle scripts, avoiding Windows .cmd quoting.
if (!process.argv.includes('--backend')) {
  run(process.execPath, [process.env.npm_execpath, 'ci'], path.join(root, 'frontend'));
}
console.log('Setup complete. Run npm run dev. PostgreSQL binaries must be installed.');
