# Examples

Run from the repo root after creating a dist/ directory:

`ash
python src/pack_basic.py ../TextSweeper/src/TSWEEP.DO dist/TSWEEP_compact.DO
python src/tokenize_basic.py dist/TSWEEP_compact.DO dist/TSWEEP_tokenized.BA 0x8001
`

Replace paths to match your source file. Outputs are byte-identical to the Tandy tokenizer.
