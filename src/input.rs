use anyhow::{anyhow, Result};
use serde::Deserialize;

#[derive(Deserialize, Debug)]
pub struct FindingsDocument {
    pub version: u8,
    pub source: String,
    pub findings: Vec<Finding>,
}

#[derive(Deserialize, Debug)]
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

#[cfg(test)]
mod tests {
    use super::*;

    fn doc_with(version: u8, source: &str, findings: &str) -> String {
        format!(
            r#"{{"version":{},"source":"{}","findings":{}}}"#,
            version, source, findings
        )
    }

    fn one_finding(id: &str, title: &str, description: &str) -> String {
        format!(
            r#"[{{"id":"{}","title":"{}","description":"{}"}}]"#,
            id, title, description
        )
    }

    #[test]
    fn accepts_minimal_valid() {
        let doc = doc_with(1, "test", &one_finding("a", "b", "c"));
        assert!(parse_and_validate(&doc).is_ok());
    }

    #[test]
    fn accepts_optional_fields() {
        let doc = r#"{
            "version": 1,
            "source": "nuclei",
            "findings": [{
                "id": "CVE-1",
                "title": "T",
                "description": "D",
                "target": "https://x",
                "severity": "critical",
                "metadata": {"foo": "bar"}
            }]
        }"#;
        let parsed = parse_and_validate(doc).unwrap();
        assert_eq!(parsed.findings[0].target.as_deref(), Some("https://x"));
        assert_eq!(parsed.findings[0].severity.as_deref(), Some("critical"));
        assert!(parsed.findings[0].metadata.is_some());
    }

    #[test]
    fn rejects_wrong_version() {
        let doc = doc_with(2, "test", &one_finding("a", "b", "c"));
        let err = parse_and_validate(&doc).unwrap_err().to_string();
        assert!(err.contains("version"), "got: {}", err);
    }

    #[test]
    fn rejects_empty_source() {
        let doc = doc_with(1, "", &one_finding("a", "b", "c"));
        assert!(parse_and_validate(&doc).is_err());
    }

    #[test]
    fn rejects_whitespace_source() {
        let doc = doc_with(1, "   ", &one_finding("a", "b", "c"));
        assert!(parse_and_validate(&doc).is_err());
    }

    #[test]
    fn rejects_empty_findings() {
        let doc = doc_with(1, "test", "[]");
        let err = parse_and_validate(&doc).unwrap_err().to_string();
        assert!(err.contains("findings"), "got: {}", err);
    }

    #[test]
    fn rejects_empty_id() {
        let doc = doc_with(1, "test", &one_finding("", "b", "c"));
        let err = parse_and_validate(&doc).unwrap_err().to_string();
        assert!(err.contains("id"), "got: {}", err);
    }

    #[test]
    fn rejects_empty_title() {
        let doc = doc_with(1, "test", &one_finding("a", "", "c"));
        let err = parse_and_validate(&doc).unwrap_err().to_string();
        assert!(err.contains("title"), "got: {}", err);
    }

    #[test]
    fn rejects_empty_description() {
        let doc = doc_with(1, "test", &one_finding("a", "b", ""));
        let err = parse_and_validate(&doc).unwrap_err().to_string();
        assert!(err.contains("description"), "got: {}", err);
    }

    #[test]
    fn rejects_malformed_json() {
        assert!(parse_and_validate("{not json").is_err());
    }

    #[test]
    fn rejects_missing_required_field() {
        let doc = r#"{"version":1,"findings":[]}"#;
        assert!(parse_and_validate(doc).is_err());
    }
}
