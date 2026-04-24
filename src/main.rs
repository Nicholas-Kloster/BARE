mod corpus;
mod input;
mod output;

use std::io::Read;

static CORPUS_BYTES: &[u8] = include_bytes!("../corpus.bin");

use anyhow::{anyhow, Context, Result};
use candle_core::{DType, Device, Tensor};
use candle_nn::VarBuilder;
use candle_transformers::models::bert::{BertModel, Config, DTYPE};
use hf_hub::{api::tokio::Api, Repo, RepoType};
use sha2::{Digest, Sha256};
use tokenizers::Tokenizer;

const MODEL_ID: &str = "sentence-transformers/all-MiniLM-L6-v2";

fn corpus_sha256() -> String {
    let mut hasher = Sha256::new();
    hasher.update(CORPUS_BYTES);
    format!("{:x}", hasher.finalize())
}

fn encode_text(
    text: &str,
    tokenizer: &Tokenizer,
    model: &BertModel,
    device: &Device,
) -> Result<Vec<f32>> {
    let encoding = tokenizer
        .encode(text, true)
        .map_err(|e| anyhow!("tokenization failed: {}", e))?;

    let input_ids      = Tensor::new(encoding.get_ids(), device)?.unsqueeze(0)?;
    let attention_mask = Tensor::new(encoding.get_attention_mask(), device)?.unsqueeze(0)?;
    let token_type_ids = Tensor::new(encoding.get_type_ids(), device)?.unsqueeze(0)?;

    let output = model.forward(&input_ids, &token_type_ids, Some(&attention_mask))?;

    let mask        = attention_mask.unsqueeze(2)?.to_dtype(DType::F32)?;
    let sum         = output.broadcast_mul(&mask)?.sum(1)?;
    let count       = mask.sum(1)?;
    let mean_pooled = sum.broadcast_div(&count)?;
    let norm        = mean_pooled.sqr()?.sum_keepdim(1)?.sqrt()?;
    let normalized  = mean_pooled.broadcast_div(&norm)?;

    Ok(normalized.squeeze(0)?.to_vec1()?)
}

fn category_from_module(name: &str) -> String {
    name.splitn(2, '_').next().unwrap_or("unknown").to_string()
}

#[tokio::main]
async fn main() -> Result<()> {
    // ── CLI parsing ───────────────────────────────────────────────────────────
    let args: Vec<String> = std::env::args().collect();
    let mut top_k: usize = 3;
    let mut input_path: Option<String> = None;
    let mut i = 1;

    while i < args.len() {
        match args[i].as_str() {
            "--version" => {
                println!("bare v1.0 (input v1, output v1)");
                return Ok(());
            }
            "--top" => {
                i += 1;
                top_k = args
                    .get(i)
                    .ok_or_else(|| anyhow!("--top requires an argument"))?
                    .parse::<usize>()
                    .context("--top value must be a positive integer")?;
            }
            arg if !arg.starts_with('-') => {
                input_path = Some(arg.to_string());
            }
            arg => {
                eprintln!("bare: unknown flag: {}", arg);
                std::process::exit(1);
            }
        }
        i += 1;
    }

    // ── Read input ────────────────────────────────────────────────────────────
    let raw_input = match &input_path {
        Some(path) => std::fs::read_to_string(path)
            .with_context(|| format!("cannot read {}", path))?,
        None => {
            let mut buf = String::new();
            std::io::stdin()
                .read_to_string(&mut buf)
                .context("reading stdin failed")?;
            buf
        }
    };

    let doc = input::parse_and_validate(&raw_input).context("input validation failed")?;

    // ── Model setup ───────────────────────────────────────────────────────────
    let device = Device::Cpu;

    eprintln!("[1/3] Resolving model files...");
    let api  = Api::new()?;
    let repo = api.repo(Repo::new(MODEL_ID.to_string(), RepoType::Model));
    let tokenizer_path = repo.get("tokenizer.json").await?;
    let weights_path   = repo.get("model.safetensors").await?;
    let config_path    = repo.get("config.json").await?;
    eprintln!("[+] Files ready.");

    eprintln!("[2/3] Loading tokenizer...");
    let tokenizer = Tokenizer::from_file(tokenizer_path)
        .map_err(|e| anyhow!("tokenizer load failed: {}", e))?;

    eprintln!("[3/3] Loading model weights...");
    let config_str = std::fs::read_to_string(config_path)?;
    let config: Config = serde_json::from_str(&config_str)?;
    let vb = unsafe { VarBuilder::from_mmaped_safetensors(&[weights_path], DTYPE, &device)? };
    let model = BertModel::load(vb, &config)?;
    eprintln!("[+] Model loaded.");

    // ── Load corpus ───────────────────────────────────────────────────────────
    let records = corpus::load_corpus(CORPUS_BYTES)?;
    eprintln!("[+] Corpus: {} records", records.len());

    let sha256 = corpus_sha256();

    // ── Process each finding ──────────────────────────────────────────────────
    let mut output_findings = Vec::with_capacity(doc.findings.len());

    for finding in &doc.findings {
        eprintln!("[*] Encoding: {}", finding.id);
        let query_vec = encode_text(&finding.description, &tokenizer, &model, &device)?;

        let mut scores: Vec<(&str, f32)> = records
            .iter()
            .map(|r| {
                let sim: f32 = query_vec.iter().zip(r.vector.iter()).map(|(a, b)| a * b).sum();
                (r.name.as_str(), sim)
            })
            .collect();

        scores.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));

        let matches: Vec<output::Match> = scores
            .iter()
            .take(top_k)
            .enumerate()
            .map(|(idx, (name, score))| output::Match {
                rank:     idx + 1,
                module:   name.to_string(),
                score:    *score,
                category: category_from_module(name),
            })
            .collect();

        output_findings.push(output::OutputFinding {
            id:       finding.id.clone(),
            title:    finding.title.clone(),
            target:   finding.target.clone(),
            severity: finding.severity.clone(),
            matches,
        });
    }

    // ── Emit output ───────────────────────────────────────────────────────────
    let out_doc = output::OutputDocument {
        version: 1,
        source:  "bare".to_string(),
        corpus:  output::CorpusMeta {
            size:   records.len(),
            sha256,
        },
        findings: output_findings,
    };

    println!("{}", serde_json::to_string_pretty(&out_doc)?);

    Ok(())
}
