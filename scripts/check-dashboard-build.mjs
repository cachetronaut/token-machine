import { execFileSync } from "node:child_process";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const jsDir = "src/token_machine/dashboard/assets/js";

function snapshot() {
  return new Map(
    readdirSync(jsDir)
      .filter((name) => name.endsWith(".js"))
      .map((name) => [name, readFileSync(join(jsDir, name), "utf8")]),
  );
}

const before = snapshot();
execFileSync("pnpm", ["exec", "tsc", "-p", "tsconfig.json"], { stdio: "inherit" });
const after = snapshot();

const changed = [];
for (const [name, content] of after) {
  if (before.get(name) !== content) {
    changed.push(name);
  }
}

for (const name of before.keys()) {
  if (!after.has(name)) {
    changed.push(name);
  }
}

if (changed.length) {
  console.error(`Dashboard build output is stale: ${[...new Set(changed)].sort().join(", ")}`);
  process.exit(1);
}
