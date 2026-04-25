mod corpus;
mod input;
mod output;

use std::io::Read;

static CORPUS_BYTES:    &[u8] = include_bytes!("../corpus.bin");
static TOKENIZER_BYTES: &[u8] = include_bytes!("../assets/tokenizer.json");
static CONFIG_BYTES:    &[u8] = include_bytes!("../assets/config.json");
static WEIGHTS_BYTES:   &[u8] = include_bytes!("../assets/model.safetensors");

const BANNER: &str = r#"
    ____  ___    ____  ______
   / __ )/   |  / __ \/ ____/
  / __  / /| | / /_/ / __/
 / /_/ / ___ |/ _, _/ /___
/_____/_/  |_/_/ |_/_____/   v{VERSION}

                           by NuClide
"#;

const HELP: &str = r#"BARE — Binary Anywhere Rust Encoder

Semantic search for security scanner findings against an embedded
Metasploit corpus. Reads findings.json (BARE input schema v1) on
stdin or from a file, emits ranked module matches as JSON on stdout.

USAGE:
    bare [OPTIONS] [INPUT_PATH]

OPTIONS:
    --top <N>    Number of top matches to return per finding (default: 3,
                 capped to corpus size).
    --encode     Read text from stdin, print L2-normalized 384-dim vector
                 to stdout (space-separated). Used for parity testing
                 against Python sentence-transformers.
    --version    Print version banner and exit.
    --help       Print this help and exit.

INPUT:
    INPUT_PATH may be a path to a findings.json file, or "-" / omitted
    to read from stdin. See INPUT_FORMAT.md for the full schema.

OUTPUT:
    Pretty-printed JSON document on stdout. See OUTPUT_FORMAT.md.
    Status messages and warnings are written to stderr.

EXAMPLES:
    nuclei -u https://target -j | python adapters/nuclei/nuclei_to_bare.py | bare
    bare --top 5 findings.json
    bare < findings.json
"#;

use anyhow::{anyhow, Context, Result};
use candle_core::{DType, Device, Tensor};
use candle_nn::VarBuilder;
use candle_transformers::models::bert::{BertModel, Config, DTYPE};
use sha2::{Digest, Sha256};
use tokenizers::Tokenizer;

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

fn main() -> Result<()> {
    // ── CLI parsing ───────────────────────────────────────────────────────────
    let args: Vec<String> = std::env::args().collect();
    let mut top_k: usize = 3;
    let mut input_path: Option<String> = None;
    let mut encode_only = false;
    let mut i = 1;

    while i < args.len() {
        match args[i].as_str() {
            "--version" | "-V" => {
                let banner = BANNER.replace("{VERSION}", env!("CARGO_PKG_VERSION"));
                eprintln!("{}", banner);
                return Ok(());
            }
            "--help" | "-h" => {
                println!("{}", HELP);
                return Ok(());
            }
            "--top" => {
                i += 1;
                top_k = args
                    .get(i)
                    .ok_or_else(|| anyhow!("--top requires an argument"))?
                    .parse::<usize>()
                    .context("--top value must be a positive integer")?;
                if top_k == 0 {
                    return Err(anyhow!("--top must be >= 1"));
                }
            }
            "--encode" => {
                encode_only = true;
            }
            "-" => {
                // Explicit stdin marker — leave input_path as None
            }
            arg if !arg.starts_with('-') => {
                input_path = Some(arg.to_string());
            }
            arg => {
                eprintln!("bare: unknown flag: {}\n\nRun 'bare --help' for usage.", arg);
                std::process::exit(1);
            }
        }
        i += 1;
    }

    // ── Encode-only mode (parity testing) ─────────────────────────────────────
    // Reads text from stdin, prints space-separated f32 vector to stdout.
    // Used by the CI parity check to compare against Python sentence-transformers.
    if encode_only {
        let device = Device::Cpu;
        let tokenizer = Tokenizer::from_bytes(TOKENIZER_BYTES)
            .map_err(|e| anyhow!("tokenizer load failed: {}", e))?;
        let config: Config = serde_json::from_slice(CONFIG_BYTES)?;
        let vb = VarBuilder::from_buffered_safetensors(WEIGHTS_BYTES.to_vec(), DTYPE, &device)?;
        let model = BertModel::load(vb, &config)?;

        let mut text = String::new();
        std::io::stdin()
            .read_to_string(&mut text)
            .context("reading stdin failed")?;
        let text = text.trim();
        if text.is_empty() {
            return Err(anyhow!("--encode requires non-empty text on stdin"));
        }

        let vec = encode_text(text, &tokenizer, &model, &device)?;
        let line: Vec<String> = vec.iter().map(|x| format!("{:.10}", x)).collect();
        println!("{}", line.join(" "));
        return Ok(());
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

    // ── Load embedded model assets ────────────────────────────────────────────
    let device = Device::Cpu;

    eprintln!("[1/3] Loading tokenizer...");
    let tokenizer = Tokenizer::from_bytes(TOKENIZER_BYTES)
        .map_err(|e| anyhow!("tokenizer load failed: {}", e))?;

    eprintln!("[2/3] Loading model weights...");
    let config: Config = serde_json::from_slice(CONFIG_BYTES)?;
    let vb = VarBuilder::from_buffered_safetensors(WEIGHTS_BYTES.to_vec(), DTYPE, &device)?;
    let model = BertModel::load(vb, &config)?;
    eprintln!("[+] Model loaded.");

    // ── Load embedded corpus ──────────────────────────────────────────────────
    let records = corpus::load_corpus(CORPUS_BYTES)?;
    eprintln!("[+] Corpus: {} records", records.len());

    if top_k > records.len() {
        eprintln!(
            "[warn] --top {} exceeds corpus size {}, capping",
            top_k,
            records.len()
        );
        top_k = records.len();
    }

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
