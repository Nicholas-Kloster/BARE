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
    /// Set when --no-match-threshold fires: top corpus score fell below the
    /// threshold, meaning the msf corpus has no meaningful coverage for this
    /// finding class (e.g. Open WebUI / LiteLLM / Ollama). Downstream tools
    /// should treat this finding as unranked rather than using the low-score
    /// noise matches.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub no_high_confidence_match: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub no_match_reason: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub top_score_seen: Option<f32>,
}

#[derive(Serialize)]
pub struct Match {
    pub rank: usize,
    pub module: String,
    pub score: f32,
    pub category: String,
}
