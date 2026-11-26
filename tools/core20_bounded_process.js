"use strict";

const fs = require("fs");
const { spawn, spawnSync } = require("child_process");

function finish(payload, code) {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
  process.exitCode = code;
}

if (process.argv.length !== 3) {
  finish({ schema: "estakada.core20-process-v1", error: "REQUEST_REQUIRED" }, 2);
} else {
  let request;
  try {
    request = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
  } catch {
    finish({ schema: "estakada.core20-process-v1", error: "REQUEST_INVALID" }, 2);
  }

  if (request) {
    const valid =
      request.schema === "estakada.core20-process-request-v1" &&
      typeof request.file === "string" && request.file.length > 0 &&
      typeof request.taskkill === "string" && request.taskkill.length > 0 &&
      Array.isArray(request.args) && request.args.every((value) => typeof value === "string") &&
      Number.isInteger(request.timeoutMs) && request.timeoutMs >= 1000 && request.timeoutMs <= 600000 &&
      Number.isInteger(request.maxOutputBytes) && request.maxOutputBytes >= 1024 && request.maxOutputBytes <= 2097152;
    if (!valid) {
      finish({ schema: "estakada.core20-process-v1", error: "REQUEST_INVALID" }, 2);
    } else {
      const child = spawn(request.file, request.args, {
        windowsHide: true,
        shell: false,
        stdio: ["ignore", "pipe", "pipe"],
      });
      const stdout = [];
      const stderr = [];
      let stdoutBytes = 0;
      let stderrBytes = 0;
      let totalBytes = 0;
      let overflow = false;
      let timedOut = false;
      let settled = false;

      const terminateTree = () => {
        if (!child.pid) return;
        if (process.platform === "win32") {
          spawnSync(request.taskkill, ["/PID", String(child.pid), "/T", "/F"], {
            windowsHide: true,
            timeout: 5000,
            stdio: "ignore",
          });
        } else {
          try { process.kill(-child.pid, "SIGKILL"); } catch {}
          try { child.kill("SIGKILL"); } catch {}
        }
      };

      const collect = (chunks, currentBytes, chunk) => {
        const remaining = request.maxOutputBytes - totalBytes;
        if (remaining <= 0 || chunk.length > remaining) {
          overflow = true;
          terminateTree();
          return currentBytes;
        }
        chunks.push(chunk);
        totalBytes += chunk.length;
        return currentBytes + chunk.length;
      };
      child.stdout.on("data", (chunk) => { stdoutBytes = collect(stdout, stdoutBytes, chunk); });
      child.stderr.on("data", (chunk) => { stderrBytes = collect(stderr, stderrBytes, chunk); });

      const timer = setTimeout(() => {
        timedOut = true;
        terminateTree();
      }, request.timeoutMs);

      const settle = (exitCode, signal, spawnError) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        finish({
          schema: "estakada.core20-process-v1",
          exitCode: Number.isInteger(exitCode) ? exitCode : null,
          signal: signal || null,
          timedOut,
          overflow,
          spawnError: spawnError || null,
          stdout: Buffer.concat(stdout).toString("utf8"),
          stderr: Buffer.concat(stderr).toString("utf8"),
        }, 0);
      };
      child.on("error", (error) => settle(null, null, error.code || "SPAWN_ERROR"));
      child.on("close", (code, signal) => settle(code, signal, null));
    }
  }
}
