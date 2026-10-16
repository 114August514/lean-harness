use std::fs;

fn add(a: i32, b: i32) -> i32 {
    a + b
}

fn main() {
    println!("=======================================================");
    println!("🚀 Rust Tracer Bullet Ready");
    let seeds = fs::read_to_string("data/demo_seeds.json").unwrap_or_default();
    println!("📦 Seed file length: {} bytes", seeds.len());
    println!("=======================================================");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add() {
        assert_eq!(add(1, 2), 3);
    }
}
