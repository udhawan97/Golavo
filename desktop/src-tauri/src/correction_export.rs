//! Narrow native export bridge for already-built correction JSON.
//!
//! The frontend supplies only a content-addressed export id. The source path is
//! derived under Application Support and the destination comes exclusively from
//! the native save dialog, preventing arbitrary file reads or writes via IPC.

use std::path::PathBuf;

use serde_json::Value;
use tauri::{AppHandle, Manager, Runtime};

const NAMESPACES: &[&str] = &[
    "core-cc0",
    "enrichment-cc0",
    "enrichment-public-domain",
    "enrichment-cc-by-4.0",
];

fn valid_export_id(value: &str) -> bool {
    value.len() == 67
        && value.starts_with("cx_")
        && value[3..]
            .bytes()
            .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase())
}

fn export_source<R: Runtime>(app: &AppHandle<R>, export_id: &str) -> Result<PathBuf, String> {
    if !valid_export_id(export_id) {
        return Err("invalid correction export id".into());
    }
    let root = app
        .path()
        .app_local_data_dir()
        .map_err(|error| error.to_string())?
        .join("corrections")
        .join("exports");
    let filename = format!("{export_id}.golavo-correction.json");
    for namespace in NAMESPACES {
        let candidate = root.join(namespace).join(&filename);
        let Ok(metadata) = std::fs::symlink_metadata(&candidate) else {
            continue;
        };
        if !metadata.is_file() || metadata.file_type().is_symlink() || metadata.len() > 1_048_576 {
            return Err("correction export is not a safe regular file".into());
        }
        let bytes = std::fs::read(&candidate).map_err(|error| error.to_string())?;
        let payload: Value = serde_json::from_slice(&bytes)
            .map_err(|_| "correction export is not valid JSON".to_string())?;
        if payload.get("export_id").and_then(Value::as_str) != Some(export_id)
            || payload.get("license_namespace").and_then(Value::as_str) == Some("overlay-odbl-1.0")
        {
            return Err("correction export identity or license boundary is invalid".into());
        }
        return Ok(candidate);
    }
    Err("correction export was not found".into())
}

#[tauri::command]
pub fn save_correction_export<R: Runtime>(
    app: AppHandle<R>,
    export_id: String,
) -> Result<Option<String>, String> {
    let source = export_source(&app, &export_id)?;
    let filename = format!("{export_id}.golavo-correction.json");
    let Some(destination) = rfd::FileDialog::new()
        .set_title("Export correction proposal")
        .set_file_name(&filename)
        .add_filter("Golavo correction", &["json"])
        .save_file()
    else {
        return Ok(None);
    };
    std::fs::copy(source, &destination)
        .map_err(|error| format!("could not save correction export: {error}"))?;
    Ok(Some(destination.to_string_lossy().to_string()))
}

#[cfg(test)]
mod tests {
    use super::valid_export_id;

    #[test]
    fn export_id_is_content_addressed_and_lowercase() {
        assert!(valid_export_id(&format!("cx_{}", "a".repeat(64))));
        assert!(!valid_export_id(&format!("cx_{}", "A".repeat(64))));
        assert!(!valid_export_id("../../private"));
        assert!(!valid_export_id(&format!("ev_{}", "a".repeat(64))));
    }
}
