//! Tracer bullet: load the demo seed data and print a summary.

use serde_json::Value;
use std::{env, fs, process};

const SEED_PATH: &str = "data/demo_seeds.json";

/// Parses a JSON array of seed items.
fn load_seeds(data: &str) -> Result<Vec<Value>, String> {
    match serde_json::from_str(data).map_err(|e| e.to_string())? {
        Value::Array(items) => Ok(items),
        _ => Err("expected a JSON array".to_string()),
    }
}

fn run() -> Result<(), String> {
    let data = fs::read_to_string(SEED_PATH).map_err(|e| format!("{SEED_PATH}: {e}"))?;
    let seeds = load_seeds(&data)?;
    if env::args().nth(1).as_deref() == Some("seed") {
        println!("Loaded {} seed items from {SEED_PATH}", seeds.len());
        return Ok(());
    }
    println!("Tracer bullet ready: {} seed items", seeds.len());
    for item in seeds.iter().take(3) {
        let id = item["id"].as_str().unwrap_or("?");
        let title = item["title"].as_str().unwrap_or("");
        println!("  - [{id}] {title}");
    }
    Ok(())
}

fn main() {
    if let Err(err) = run() {
        eprintln!("error: {err}");
        process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reads_items() {
        let items = load_seeds(r#"[{"id": "a", "title": "A"}]"#).unwrap();
        assert_eq!(items.len(), 1);
        assert_eq!(items[0]["title"], "A");
    }

    #[test]
    fn rejects_non_array() {
        assert!(load_seeds(r#"{"id": "a"}"#).is_err());
    }
}
