# Near-break-even product trials

Six products have editable dimensioned drawings and physically measurable acceptance tests. Each trial compares a candidate with a changed design or operating assumption that fails a named criterion.

| Product | Design question |
| --- | --- |
| [P082 crossbeam coupon](P082/README.md) | Does a supported coupon keep deadweight deflection within 0.08 mm? |
| [P220 large-ball pointer](P220/README.md) | Does the deadband suppress stationary noise and still allow a short drag? |
| [P237 backing board pair](P237/README.md) | Do the opposed bevels give symmetric shoulders? |
| [P243 stitch groover](P243/README.md) | How far does the center groove depart from its offset on curved guides? |
| [P266 spouted portafilter cradle](P266/README.md) | Does the cradle seat the assumed body while clearing the spouts? |
| [P270 three-lane label dispenser](P270/README.md) | Does liner geometry allow a distinct peel path across all lanes? |

Use Python 3.10 or later.

```bash
cd projects/engineering-opportunity-portfolio/catalog/engineering/margin-wave
python3 verify.py
```

The verifier reads the saved drawings and scripted traces, checks the candidate and its negative control, and rebuilds in a temporary directory to detect stale exports. [Editable inputs](designs.json) and [numeric evidence](results.json) include both variants. Setup and physical acceptance details live in each product report.
