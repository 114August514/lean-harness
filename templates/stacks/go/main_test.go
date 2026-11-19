package main

import "testing"

func TestLoadSeedsReadsItems(t *testing.T) {
	items, err := LoadSeeds([]byte(`[{"id": "a", "title": "A"}]`))
	if err != nil {
		t.Fatal(err)
	}
	if len(items) != 1 || items[0].ID != "a" || items[0].Title != "A" {
		t.Fatalf("unexpected items: %+v", items)
	}
}

func TestLoadSeedsRejectsNonArray(t *testing.T) {
	if _, err := LoadSeeds([]byte(`{"id": "a"}`)); err == nil {
		t.Fatal("expected an error for a non-array document")
	}
}
