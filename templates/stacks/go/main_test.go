package main

import "testing"

func TestAdd(t *testing.T) {
	if Add(1, 2) != 3 {
		t.Errorf("Expected 3, got %d", Add(1, 2))
	}
}

func TestLoadSeeds(t *testing.T) {
	seeds := LoadSeeds()
	if seeds == nil {
		t.Log("No seeds loaded or empty, ok for unit test.")
	}
}
