// Command lean-app is the tracer bullet: it loads the demo seed data and
// prints a summary.
package main

import (
	"encoding/json"
	"fmt"
	"os"
)

const seedPath = "data/demo_seeds.json"

// SeedItem is one entry of data/demo_seeds.json.
type SeedItem struct {
	ID    string `json:"id"`
	Title string `json:"title"`
}

// LoadSeeds parses a JSON array of seed items.
func LoadSeeds(data []byte) ([]SeedItem, error) {
	var items []SeedItem
	if err := json.Unmarshal(data, &items); err != nil {
		return nil, fmt.Errorf("parse seeds: %w", err)
	}
	return items, nil
}

func run(args []string) error {
	data, err := os.ReadFile(seedPath)
	if err != nil {
		return err
	}
	seeds, err := LoadSeeds(data)
	if err != nil {
		return err
	}
	if len(args) == 1 && args[0] == "seed" {
		fmt.Printf("Loaded %d seed items from %s\n", len(seeds), seedPath)
		return nil
	}
	fmt.Printf("Tracer bullet ready: %d seed items\n", len(seeds))
	for i, item := range seeds {
		if i == 3 {
			break
		}
		fmt.Printf("  - [%s] %s\n", item.ID, item.Title)
	}
	return nil
}

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
}
