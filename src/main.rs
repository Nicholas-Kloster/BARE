/// main.rs
/// ────────
/// Proof of concept — BERT inference in Rust.
///
/// Does exactly one thing:
///   1. Downloads all-MiniLM-L6-v2 from HuggingFace
///   2. Tokenizes the query
///   3. Runs a forward pass through the model
///   4. Mean pools the output (same as sentence-transformers)
///   5. L2 normalizes the vector
///   6. Prints the first 5 floats
///
/// If those 5 floats match baseline.py — the idea works.
///
/// Usage:
///   cargo run --release

use anyhow::{Ok, Result};
use candle_core::{DType, Device, Tensor};
use candle_nn::VarBuilder;
use candle_transformers::models::bert::{BertModel, Config, DTYPE};
use hf_hub::{api::tokio::Api, Repo, RepoType};
use tokenizers::Tokenizer;

// ── The sentence we're encoding ───────────────────────────────────────────────
// Change this to match whatever you ran in baseline.py
const QUERY: &str = "unauthenticated ollama api endpoint";

// ── Model on HuggingFace Hub ──────────────────────────────────────────────────
const MODEL_ID: &str = "sentence-transformers/all-MiniLM-L6-v2";

#[tokio::main]
async fn main() -> Result<()> {
    println!("\n── BERT Rust Proof of Concept ───────────────────");
    println!("   Query : \"{}\"", QUERY);
    println!("   Model : {}", MODEL_ID);
    println!("─────────────────────────────────────────────────\n");

    let device = Device::Cpu;

    // ── Step 1: Download model files from HuggingFace ─────────────────────────
    println!("[1/4] Downloading model files...");
    println!("      (cached after first run — stored in ~/.cache/huggingface)");

    let api  = Api::new()?;
    let repo = api.repo(Repo::new(MODEL_ID.to_string(), RepoType::Model));

    let tokenizer_path = repo.get("tokenizer.json").await?;
    let weights_path   = repo.get("model.safetensors").await?;
    let config_path    = repo.get("config.json").await?;

    println!("[+] Files ready.\n");

    // ── Step 2: Load tokenizer ────────────────────────────────────────────────
    println!("[2/4] Loading tokenizer...");

    let tokenizer = Tokenizer::from_file(tokenizer_path)
        .map_err(|e| anyhow::anyhow!("Tokenizer load failed: {}", e))?;

    // ── Step 3: Load model ────────────────────────────────────────────────────
    println!("[3/4] Loading model weights...");

    let config_str = std::fs::read_to_string(config_path)?;
    let config: Config = serde_json::from_str(&config_str)?;

    let vb = unsafe {
        VarBuilder::from_mmaped_safetensors(
            &[weights_path],
            DTYPE,
            &device,
        )?
    };

    let model = BertModel::load(vb, &config)?;
    println!("[+] Model loaded.\n");

    // ── Step 4: Tokenize the query ────────────────────────────────────────────
    println!("[4/4] Encoding query...");

    let encoding = tokenizer
        .encode(QUERY, true)
        .map_err(|e| anyhow::anyhow!("Tokenization failed: {}", e))?;

    // Show what the tokenizer produced — useful for debugging mismatches
    println!("      Tokens : {:?}", encoding.get_tokens());
    println!("      IDs    : {:?}", encoding.get_ids());

    // Convert to tensors — batch size of 1
    let input_ids = Tensor::new(encoding.get_ids(), &device)?
        .unsqueeze(0)?;                                        // [1, seq_len]

    let attention_mask = Tensor::new(encoding.get_attention_mask(), &device)?
        .unsqueeze(0)?;                                        // [1, seq_len]

    let token_type_ids = Tensor::new(encoding.get_type_ids(), &device)?
        .unsqueeze(0)?;                                        // [1, seq_len]

    // ── Step 5: Forward pass ──────────────────────────────────────────────────
    // output shape: [1, seq_len, hidden_size]  (hidden_size = 384 for MiniLM)
    let output = model.forward(&input_ids, &token_type_ids, Some(&attention_mask))?;

    // ── Step 6: Mean pooling ──────────────────────────────────────────────────
    // This is what sentence-transformers does — NOT just taking the [CLS] token.
    // Multiply each token embedding by its attention mask (1 or 0)
    // Sum across sequence length, divide by number of real tokens.
    //
    // Matching this exactly is what makes our vectors agree with Python.

    let mask = attention_mask
        .unsqueeze(2)?                    // [1, seq_len, 1] — broadcast over hidden dim
        .to_dtype(DType::F32)?;

    let masked_output = output.broadcast_mul(&mask)?;     // zero out padding tokens

    // Sum over sequence length dimension
    let sum   = masked_output.sum(1)?;                    // [1, hidden_size]
    let count = mask.sum(1)?;                             // [1, 1] — number of real tokens

    let mean_pooled = sum.broadcast_div(&count)?;         // [1, hidden_size]

    // ── Step 7: L2 normalization ──────────────────────────────────────────────
    // Makes vectors comparable with cosine similarity via dot product alone.
    let norm = mean_pooled
        .sqr()?
        .sum_keepdim(1)?
        .sqrt()?;                                         // [1, 1]

    let normalized = mean_pooled.broadcast_div(&norm)?;   // [1, hidden_size]

    // ── Step 8: Extract and print ─────────────────────────────────────────────
    let vec: Vec<f32> = normalized.squeeze(0)?.to_vec1()?;

    // Verify the norm is ~1.0 (sanity check)
    let l2_norm: f32 = vec.iter().map(|x| x * x).sum::<f32>().sqrt();

    println!("\n── Results ──────────────────────────────────────");
    println!("   Vector length : {}", vec.len());
    println!("   First 5 floats: {:?}", &vec[..5]);
    println!("   Last 5 floats : {:?}", &vec[vec.len()-5..]);
    println!("   L2 norm       : {:.6}  (should be ~1.0)", l2_norm);
    println!("─────────────────────────────────────────────────");
    println!("\n   Compare first 5 floats to baseline.py output.");
    println!("   If they match — the idea works.\n");

    Ok(())
}
