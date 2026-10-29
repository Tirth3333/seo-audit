# Demo reports

| File | Label | How it was produced |
|---|---|---|
| `synthetic-shop-example.{csv,pdf}` and `backend/demo_data/synthetic-shop-example.json` | **SYNTHETIC** | `python -m scripts.make_synthetic_demo` — the real crawler and rules run against `shop.example.com`, a fictional website served from memory (`backend/tests/fixtures/site.py`) with deliberate SEO problems. Findings are genuine tool output for that fixture, **not observations of any real company**. |

## Real-company demo — pending

No real website could be crawled in the development environment (no outbound internet). To produce one on a machine with internet access, for a site you are permitted to audit:

```bash
cd backend
python -m scripts.run_audit https://www.example-company.com --max-pages 25 --max-depth 2
```

The JSON, CSV and PDF land here with the real audit timestamp, tested URLs, crawl status and limitations, labelled `live`. Commit them only after reviewing the findings.
