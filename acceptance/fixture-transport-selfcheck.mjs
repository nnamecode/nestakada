// Stdio transport test double ONLY. Never exports app actors/profiles/business behavior.
let input = '';
for await (const chunk of process.stdin) input += chunk;
const request = JSON.parse(input);
const mode = request.args?.transportMode || 'echo';
if (mode === 'ignore-term') {
  process.on('SIGTERM', () => {});
  await new Promise(resolve => setTimeout(resolve, 30_000));
}
if (mode === 'slow') await new Promise(resolve => setTimeout(resolve, 30_000));
if (mode === 'stderr-flood') process.stderr.write('x'.repeat(1100000));
if (mode === 'process-error') { process.stderr.write('SYNTHETIC-SECRET-MUST-NOT-LEAK'); process.exit(3); }
if (mode === 'bad-json') { process.stdout.write('not-json'); process.exit(0); }
process.stdout.write(JSON.stringify({
  protocol: request.protocol,
  nonce: mode === 'wrong-nonce' ? 'wrong' : request.nonce,
  ok: true,
  targetOrigin: request.targetOrigin,
  runId: mode === 'wrong-run' ? 'other-run' : request.runId,
  source: 'transport-selfcheck',
  data: mode === 'stdout-flood' ? 'x'.repeat(1100000) : request.args?.value,
}));
