# BARE Corpus Binary Format v1

Little-endian. No padding. No alignment assumptions.

## Header (11 bytes)

| Offset | Size | Type | Description              |
|--------|------|------|--------------------------|
| 0      | 4    | u8[] | Magic bytes: "BARE"      |
| 4      | 1    | u8   | Format version: 0x01     |
| 5      | 2    | u16  | Vector dimensions (384)  |
| 7      | 4    | u32  | Record count (N)         |

## Records (N records follow header)

| Offset  | Size       | Type   | Description              |
|---------|------------|--------|--------------------------|
| 0       | 2          | u16    | Name length in bytes     |
| 2       | name_len   | u8[]   | Name as UTF-8            |
| 2+len   | dims × 4   | f32[]  | Vector, little-endian    |

## Validation

Readers must verify:
1. First 4 bytes == "BARE"
2. Version byte == 0x01
3. Dimensions == 384 (for MiniLM-L6-v2)
4. File length matches: 11 + sum(2 + name_len + dims*4) across all records
