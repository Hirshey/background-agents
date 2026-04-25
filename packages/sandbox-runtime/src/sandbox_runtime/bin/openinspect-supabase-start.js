#!/usr/bin/env node
import { spawn, spawnSync } from "node:child_process";

function run(command, args) {
  return spawnSync(command, args, {
    env: process.env,
    stdio: "inherit",
  }).status;
}

const dockerStatus = run("openinspect-start-docker", []);
if (dockerStatus !== 0) {
  process.exit(dockerStatus || 1);
}

const supabaseCheck = spawnSync("supabase", ["--version"], {
  env: process.env,
  stdio: "ignore",
});
if (supabaseCheck.status !== 0) {
  console.error("supabase CLI is not installed in this sandbox image");
  process.exit(1);
}

const supabase = spawn("supabase", ["start", ...process.argv.slice(2)], {
  env: {
    ...process.env,
    SUPABASE_TELEMETRY_DISABLED: process.env.SUPABASE_TELEMETRY_DISABLED || "1",
    DO_NOT_TRACK: process.env.DO_NOT_TRACK || "1",
  },
  stdio: "inherit",
});

supabase.on("exit", (code, signal) => {
  if (signal) {
    console.error(`supabase start exited from signal ${signal}`);
    process.exit(1);
  }
  process.exit(code || 0);
});
