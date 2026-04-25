use anyhow::{anyhow, Result};

const MAGIC: &[u8; 4] = b"BARE";
const VERSION: u8 = 0x01;
const DIMS: u16 = 384;

#[derive(Debug)]
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

#[cfg(test)]
mod tests {
    use super::*;

    fn build_corpus(records: &[(&str, Vec<f32>)]) -> Vec<u8> {
        let mut buf = Vec::new();
        buf.extend_from_slice(MAGIC);
        buf.push(VERSION);
        buf.extend_from_slice(&DIMS.to_le_bytes());
        buf.extend_from_slice(&(records.len() as u32).to_le_bytes());
        for (name, vec) in records {
            buf.extend_from_slice(&(name.len() as u16).to_le_bytes());
            buf.extend_from_slice(name.as_bytes());
            for f in vec {
                buf.extend_from_slice(&f.to_le_bytes());
            }
        }
        buf
    }

    #[test]
    fn loads_valid_single_record() {
        let bytes = build_corpus(&[("module_x", vec![0.1; 384])]);
        let records = load_corpus(&bytes).unwrap();
        assert_eq!(records.len(), 1);
        assert_eq!(records[0].name, "module_x");
        assert_eq!(records[0].vector.len(), 384);
        assert!((records[0].vector[0] - 0.1).abs() < 1e-6);
    }

    #[test]
    fn loads_empty_corpus() {
        let bytes = build_corpus(&[]);
        let records = load_corpus(&bytes).unwrap();
        assert!(records.is_empty());
    }

    #[test]
    fn rejects_too_short_for_header() {
        assert!(load_corpus(&[0u8; 5]).is_err());
    }

    #[test]
    fn rejects_bad_magic() {
        let mut bytes = build_corpus(&[]);
        bytes[0] = b'X';
        let err = load_corpus(&bytes).unwrap_err().to_string();
        assert!(err.contains("magic"), "expected magic error, got: {}", err);
    }

    #[test]
    fn rejects_unsupported_version() {
        let mut bytes = build_corpus(&[]);
        bytes[4] = 0x99;
        let err = load_corpus(&bytes).unwrap_err().to_string();
        assert!(err.contains("version"), "expected version error, got: {}", err);
    }

    #[test]
    fn rejects_dimension_mismatch() {
        let mut bytes = build_corpus(&[]);
        bytes[5..7].copy_from_slice(&512u16.to_le_bytes());
        let err = load_corpus(&bytes).unwrap_err().to_string();
        assert!(err.contains("dimension"), "expected dim error, got: {}", err);
    }

    #[test]
    fn rejects_truncated_vector() {
        let mut bytes = build_corpus(&[("m", vec![0.0; 384])]);
        bytes.truncate(bytes.len() - 100);
        assert!(load_corpus(&bytes).is_err());
    }

    #[test]
    fn rejects_truncated_name() {
        let mut bytes = build_corpus(&[("longname", vec![0.0; 384])]);
        // Lie about name length so it overruns EOF
        let pos = 11;
        bytes[pos..pos + 2].copy_from_slice(&u16::MAX.to_le_bytes());
        assert!(load_corpus(&bytes).is_err());
    }

    #[test]
    fn rejects_invalid_utf8_name() {
        let mut bytes = Vec::new();
        bytes.extend_from_slice(MAGIC);
        bytes.push(VERSION);
        bytes.extend_from_slice(&DIMS.to_le_bytes());
        bytes.extend_from_slice(&1u32.to_le_bytes());
        bytes.extend_from_slice(&3u16.to_le_bytes());
        bytes.extend_from_slice(&[0xFF, 0xFE, 0xFD]); // not valid UTF-8
        bytes.extend_from_slice(&[0u8; 384 * 4]);
        let err = load_corpus(&bytes).unwrap_err().to_string();
        assert!(err.contains("UTF-8"), "expected utf8 error, got: {}", err);
    }
}
