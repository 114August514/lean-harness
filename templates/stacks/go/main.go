package main

import (
	"encoding/json"
	"fmt"
	"os"
)

type SeedItem struct {
	ID   string `json:"id"`
	Name string `json:"name"`
}

func LoadSeeds() []SeedItem {
	data, err := os.ReadFile("data/demo_seeds.json")
	if err != nil {
		return nil
	}
	var items []SeedItem
	_ = json.Unmarshal(data, &items)
	return items
}

func Add(a, b int) int {
	return a + b
}

func main() {
	seeds := LoadSeeds()
	fmt.Println("=======================================================")
	fmt.Println("🚀 Go Tracer Bullet Ready")
	fmt.Printf("📦 Preloaded Seeds: %d items\n", len(seeds))
	for i, item := range seeds {
		if i >= 3 {
			break
		}
		fmt.Printf("   - [%s] %s\n", item.ID, item.Name)
	}
	fmt.Println("=======================================================")
}
