use std::process::Command;

fn source_sha() -> String {
    let from_env = std::env::var("GOLAVO_SOURCE_SHA")
        .ok()
        .map(|value| value.trim().to_ascii_lowercase());
    let from_git = {
        Command::new("git")
            .args(["rev-parse", "HEAD"])
            .output()
            .ok()
            .filter(|output| output.status.success())
            .and_then(|output| String::from_utf8(output.stdout).ok())
            .map(|value| value.trim().to_ascii_lowercase())
    };
    if let (Some(injected), Some(checkout)) = (&from_env, &from_git) {
        assert_eq!(
            injected, checkout,
            "GOLAVO_SOURCE_SHA must match the checkout being built"
        );
    }
    let sha = from_git.or(from_env).unwrap_or_default();
    assert!(
        sha.len() == 40 && sha.bytes().all(|byte| byte.is_ascii_hexdigit()),
        "GOLAVO_SOURCE_SHA must be the 40-character source commit"
    );
    sha.to_ascii_lowercase()
}

fn main() {
    println!("cargo:rerun-if-env-changed=GOLAVO_SOURCE_SHA");
    println!("cargo:rerun-if-changed=../../.git/HEAD");
    println!("cargo:rustc-env=GOLAVO_SOURCE_SHA={}", source_sha());
    tauri_build::build()
}
