import { readFileSync } from "node:fs";

const SEED_PATH = "data/demo_seeds.json";

export type SeedItem = { id?: string; title?: string };

/** Parses a JSON array of seed items. */
export function loadSeeds(text: string): SeedItem[] {
	const items: unknown = JSON.parse(text);
	if (!Array.isArray(items)) {
		throw new Error("expected a JSON array");
	}
	return items as SeedItem[];
}

function main(args: string[]): void {
	const seeds = loadSeeds(readFileSync(SEED_PATH, "utf-8"));
	if (args[0] === "seed") {
		console.log(`Loaded ${seeds.length} seed items from ${SEED_PATH}`);
		return;
	}
	console.log(`Tracer bullet ready: ${seeds.length} seed items`);
	for (const item of seeds.slice(0, 3)) {
		console.log(`  - [${item.id ?? "?"}] ${item.title ?? ""}`);
	}
}

if (import.meta.main) {
	main(process.argv.slice(2));
}
