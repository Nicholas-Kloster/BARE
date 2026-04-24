use anyhow::{anyhow, Result};
use serde::Deserialize;

#[derive(Deserialize)]
pub struct FindingsDocument {
    pub version: u8,
    pub source: String,
    pub findings: Vec<Finding>,
}

#[derive(Deserialize)]
pub struct Finding {
    pub id: String,
    pub title: String,
    pub description: String,
    pub target: Option<String>,
    pub severity: Option<String>,
    pub metadata: Option<serde_json::Value>,
}

pub fn parse_and_validate(json: &str) -> Result<FindingsDocument> {
    let doc: FindingsDocument = serde_json::from_str(json)?;

    if doc.version != 1 {
        return Err(anyhow!(
            "unsupported input version: expected 1, got {}",
            doc.version
        ));
    }
    if doc.source.trim().is_empty() {
        return Err(anyhow!("input validation failed: source is empty"));
    }
    if doc.findings.is_empty() {
        return Err(anyhow!("input validation failed: findings array is empty"));
    }
    for (i, f) in doc.findings.iter().enumerate() {
        if f.id.trim().is_empty() {
            return Err(anyhow!("finding[{}]: id is empty", i));
        }
        if f.title.trim().is_empty() {
            return Err(anyhow!("finding[{}]: title is empty", i));
        }
        if f.description.trim().is_empty() {
            return Err(anyhow!("finding[{}]: description is empty", i));
        }
    }

    Ok(doc)
}
