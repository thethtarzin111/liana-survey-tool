import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const python = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
if (!existsSync(python)) {
  console.error('Run npm install first.');
  process.exit(1);
}
const child = spawn(python, ['-u', '-m', 'backend.scripts.local_dev',
  ...(process.argv.includes('--backend') ? ['--backend-only'] : [])], {
  cwd: root, stdio: 'inherit', env: { ...process.env, LIANA_NODE: process.execPath },
});
// The Python supervisor receives Ctrl+C too and cleans up its subprocesses.
process.on('SIGINT', () => {});
process.on('SIGTERM', () => child.kill('SIGTERM'));
child.on('error', error => { console.error(error.message); process.exitCode = 1; });
child.on('exit', code => { process.exitCode = code ?? 1; });
