# Enabot-depth product corpus

Exhaustive junk→intent product space for Hardware-Splicer capability sweeps — **not capped at 200**.

## Regenerate / sweep

```bash
make product-corpus          # writes enabot_depth_corpus.json
make sweep-product-corpus    # offline salvage scoring → /tmp/hs_product_corpus_sweep
make sweep-product-corpus-compile  # also KiCad-compiles flagged candidates
```

## Depth bar

Each product is multi-subsystem (MCU + power + sense/actuate/drive/comms), salvage-plausible, with commercial analogs. Variants expand MCU (ESP32 / Nano / Pico) and power (USB / battery).

Corpus generator: `scripts/generate_product_corpus.py`  
Sweep: `scripts/sweep_product_corpus.py`
