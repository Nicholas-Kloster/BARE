use anyhow::{anyhow, Result};

const MAGIC: &[u8; 4] = b"BARE";
const VERSION: u8 = 0x01;
const DIMS: u16 = 384;

pub struct Record {
    pub name: String,
    pub vector: Vec<f32>,
}

pub fn load_corpus(bytes: &[u8]) -> Result<Vec<Record>> {
    if bytes.len() < 11 {
        return Err(anyhow!("corpus too short: {} bytes, need at least 11", bytes.len()));
    }

    if &bytes[0..4] != MAGIC {
        return Err(anyhow!(
            "bad magic: expected {:?}, got {:?}",
            MAGIC,
            &bytes[0..4]
        ));
    }

    if bytes[4] != VERSION {
        return Err(anyhow!(
            "unsupported version: expected 0x{:02x}, got 0x{:02x}",
            VERSION,
            bytes[4]
        ));
    }

    let dims = u16::from_le_bytes([bytes[5], bytes[6]]);
    if dims != DIMS {
        return Err(anyhow!(
            "dimension mismatch: expected {}, got {}",
            DIMS,
            dims
        ));
    }

    let count = u32::from_le_bytes([bytes[7], bytes[8], bytes[9], bytes[10]]) as usize;

    let mut records = Vec::with_capacity(count);
    let mut pos = 11usize;

    for i in 0..count {
        if pos + 2 > bytes.len() {
            return Err(anyhow!("truncated at record {}: missing name length", i));
        }
        let name_len = u16::from_le_bytes([bytes[pos], bytes[pos + 1]]) as usize;
        pos += 2;

        if pos + name_len > bytes.len() {
            return Err(anyhow!("truncated at record {}: name extends past EOF", i));
        }
        let name = std::str::from_utf8(&bytes[pos..pos + name_len])
            .map_err(|e| anyhow!("record {} name is not valid UTF-8: {}", i, e))?
            .to_string();
        pos += name_len;

        let vec_bytes = dims as usize * 4;
        if pos + vec_bytes > bytes.len() {
            return Err(anyhow!("truncated at record {}: vector extends past EOF", i));
        }
        let vector: Vec<f32> = bytes[pos..pos + vec_bytes]
            .chunks_exact(4)
            .map(|b| f32::from_le_bytes([b[0], b[1], b[2], b[3]]))
            .collect();
        pos += vec_bytes;

        records.push(Record { name, vector });
    }

    Ok(records)
}
