import { readFileSync, existsSync } from "fs";

export function loadSeeds(): Array<Record<string, unknown>> {
  const seedPath = "data/demo_seeds.json";
  if (existsSync(seedPath)) {
    try {
      return JSON.parse(readFileSync(seedPath, "utf-8"));
    } catch {
      return [];
    }
  }
  return [];
}

export function runDemo(): void {
  const seeds = loadSeeds();
  console.log("=======================================================");
  console.log("🚀 TypeScript + Bun Tracer Bullet Ready");
  console.log(`📦 Preloaded Seeds: ${seeds.length} items`);
  seeds.slice(0, 3).forEach((item) => {
    console.log(`   - [${item.id ?? "N/A"}] ${item.name ?? "Item"}`);
  });
  console.log("=======================================================");
}

export function add(a: number, b: number): number {
  return a + b;
}

if (import.meta.main) {
  runDemo();
}
