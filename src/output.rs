use serde::Serialize;

#[derive(Serialize)]
pub struct OutputDocument {
    pub version: u8,
    pub source: String,
    pub corpus: CorpusMeta,
    pub findings: Vec<OutputFinding>,
}

#[derive(Serialize)]
pub struct CorpusMeta {
    pub size: usize,
    pub sha256: String,
}

#[derive(Serialize)]
pub struct OutputFinding {
    pub id: String,
    pub title: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub target: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub severity: Option<String>,
    pub matches: Vec<Match>,
}

#[derive(Serialize)]
pub struct Match {
    pub rank: usize,
    pub module: String,
    pub score: f32,
    pub category: String,
}
