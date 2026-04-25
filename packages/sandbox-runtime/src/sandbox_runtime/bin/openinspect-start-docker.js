#!/usr/bin/env node
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, openSync, closeSync } from "node:fs";

const READY_TIMEOUT_MS = Number.parseInt(process.env.DOCKER_START_TIMEOUT_MS || "30000", 10);
const STORAGE_DRIVER = process.env.DOCKERD_STORAGE_DRIVER || "vfs";

function commandExists(command) {
  const result = spawnSync("sh", ["-lc", `command -v ${command}`], { stdio: "ignore" });
  return result.status === 0;
}

function dockerReady() {
  const result = spawnSync("docker", ["info"], {
    env: process.env,
    stdio: "ignore",
    timeout: 3000,
  });
  return result.status === 0;
}

async function waitForDocker() {
  const startedAt = Date.now();
  while (Date.now() - startedAt < READY_TIMEOUT_MS) {
    if (dockerReady()) return true;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return false;
}

if (!commandExists("docker")) {
  console.error("docker CLI is not installed in this sandbox image");
  process.exit(1);
}

if (dockerReady()) {
  console.log("Docker is already running");
  process.exit(0);
}

if (!commandExists("dockerd")) {
  console.error("dockerd is not installed in this sandbox image");
  process.exit(1);
}

mkdirSync("/var/run", { recursive: true });
mkdirSync("/var/lib/docker", { recursive: true });

const logPath = process.env.DOCKERD_LOG_PATH || "/tmp/openinspect-dockerd.log";
const logFd = openSync(logPath, "a");

const extraArgs = (process.env.DOCKERD_EXTRA_ARGS || "")
  .match(/(?:[^\s"]+|"[^"]*")+/g)
  ?.map((arg) => arg.replace(/^"|"$/g, ""));

const dockerd = spawn(
  "dockerd",
  [
    "--host=unix:///var/run/docker.sock",
    `--storage-driver=${STORAGE_DRIVER}`,
    ...(extraArgs || []),
  ],
  {
    detached: true,
    env: process.env,
    stdio: ["ignore", logFd, logFd],
  }
);
dockerd.unref();
closeSync(logFd);

if (await waitForDocker()) {
  console.log("Docker is running");
  process.exit(0);
}

console.error(`Docker did not become ready; dockerd logs are at ${logPath}`);
process.exit(1);
