mod corpus;

static CORPUS_BYTES: &[u8] = include_bytes!("../corpus.bin");

use anyhow::{Ok, Result};
use candle_core::{DType, Device, Tensor};
use candle_nn::VarBuilder;
use candle_transformers::models::bert::{BertModel, Config, DTYPE};
use hf_hub::{api::tokio::Api, Repo, RepoType};
use tokenizers::Tokenizer;

const QUERIES: &[&str] = &[
    "ollama exposed no authentication",
    "wordpress sql injection vulnerability",
    "jenkins pre-auth remote code execution",
    "confluence template injection",
    "apache path traversal file read",
];

const MODEL_ID: &str = "sentence-transformers/all-MiniLM-L6-v2";

#[tokio::main]
async fn main() -> Result<()> {
    let device = Device::Cpu;

    println!("\n── BARE — Binary Anywhere Rust Encoder ──────────");
    println!("   Model  : {}", MODEL_ID);
    println!("   Corpus : {} bytes embedded", CORPUS_BYTES.len());
    println!("─────────────────────────────────────────────────\n");

    // ── Setup: download, tokenizer, model (once) ──────────────────────────────
    println!("[1/3] Downloading model files...");
    println!("      (cached after first run)");
    let api  = Api::new()?;
    let repo = api.repo(Repo::new(MODEL_ID.to_string(), RepoType::Model));
    let tokenizer_path = repo.get("tokenizer.json").await?;
    let weights_path   = repo.get("model.safetensors").await?;
    let config_path    = repo.get("config.json").await?;
    println!("[+] Files ready.\n");

    println!("[2/3] Loading tokenizer...");
    let tokenizer = Tokenizer::from_file(tokenizer_path)
        .map_err(|e| anyhow::anyhow!("Tokenizer load failed: {}", e))?;

    println!("[3/3] Loading model weights...");
    let config_str = std::fs::read_to_string(config_path)?;
    let config: Config = serde_json::from_str(&config_str)?;
    let vb = unsafe {
        VarBuilder::from_mmaped_safetensors(&[weights_path], DTYPE, &device)?
    };
    let model = BertModel::load(vb, &config)?;
    println!("[+] Model loaded.\n");

    // ── Load embedded corpus (once) ───────────────────────────────────────────
    let records = corpus::load_corpus(CORPUS_BYTES)?;
    println!("[+] Corpus: {} records loaded\n", records.len());

    // ── Encode each query and rank ────────────────────────────────────────────
    for query in QUERIES {
        let encoding = tokenizer
            .encode(*query, true)
            .map_err(|e| anyhow::anyhow!("Tokenization failed: {}", e))?;

        let input_ids = Tensor::new(encoding.get_ids(), &device)?.unsqueeze(0)?;
        let attention_mask = Tensor::new(encoding.get_attention_mask(), &device)?.unsqueeze(0)?;
        let token_type_ids = Tensor::new(encoding.get_type_ids(), &device)?.unsqueeze(0)?;

        let output = model.forward(&input_ids, &token_type_ids, Some(&attention_mask))?;

        let mask        = attention_mask.unsqueeze(2)?.to_dtype(DType::F32)?;
        let sum         = output.broadcast_mul(&mask)?.sum(1)?;
        let count       = mask.sum(1)?;
        let mean_pooled = sum.broadcast_div(&count)?;
        let norm        = mean_pooled.sqr()?.sum_keepdim(1)?.sqrt()?;
        let normalized  = mean_pooled.broadcast_div(&norm)?;

        let query_vec: Vec<f32> = normalized.squeeze(0)?.to_vec1()?;

        let mut scores: Vec<(&str, f32)> = records
            .iter()
            .map(|r| {
                let sim: f32 = query_vec.iter()
                    .zip(r.vector.iter())
                    .map(|(a, b)| a * b)
                    .sum();
                (r.name.as_str(), sim)
            })
            .collect();

        scores.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());

        println!("── Query: \"{}\"", query);
        for (rank, (name, score)) in scores.iter().take(5).enumerate() {
            println!("   #{:<2} {:.4}  {}", rank + 1, score, name);
        }
        println!();
    }

    Ok(())
}
