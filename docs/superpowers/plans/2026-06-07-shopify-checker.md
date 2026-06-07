# shopify-checker Implementation Plan (Phase 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A colleague-facing tool — one password-gated link — where the marketing team uploads a lead CSV, picks the domain column, and downloads `shopify.csv` / `not-shopify.csv` / `uncertain.csv` plus the standard report artifacts.

**Architecture:** Static HTML on GitHub Pages talks directly to Supabase Storage with the anon key, then calls a Supabase Edge Function that fires `repository_dispatch` to a GitHub Actions worker. The worker runs the Phase 1 package over the list, maps results back to the original rows, and writes outputs to the job folder. No server, no Vercel, no secret in the browser.

**Tech Stack:** Python 3.11 (worker, depends on `shopify-domain-detector@v0.1.0`), Supabase Storage + Edge Functions (Deno/TS), GitHub Actions (`repository_dispatch`), vanilla JS + PapaParse (SRI-pinned) on GitHub Pages.

**Prerequisite:** Phase 1 tagged `v0.1.0` and `pip install git+https://github.com/ahmedxomar101/shopify-domain-detector@v0.1.0` works.

---

## File Structure

```
shopify-checker/                      (NavonaAI/shopify-checker, private)
  pyproject.toml                      # worker deps incl. detector @v0.1.0
  README.md
  AGENTS.md
  .gitignore
  src/checker/
    __init__.py
    buckets.py                        # Category -> output bucket (pure)
    job.py                            # CSV in -> 3 CSVs + report + zip (core)
    storage.py                        # Supabase Storage I/O + status updates
    run.py                            # worker entrypoint (reads dispatch payload)
  supabase/functions/enqueue/index.ts # Edge Function: repository_dispatch
  web/index.html                      # static UI (GitHub Pages)
  .github/workflows/run-check.yml     # repository_dispatch worker
  .github/workflows/ci.yml            # lint + unit tests
  tests/
    test_buckets.py
    test_job.py
    test_storage.py
```

## Job data contract (Supabase Storage)

```
shopify-checks/<jobId>/
  input.csv        # uploaded by the browser
  meta.json        # {"domain_column": "...", "rows": N, "created_at": "..."}
  status.json      # {"state": "queued|running|done|failed", "progress": 0-100, "error": null}
  shopify.csv      # outputs (written by worker)
  not-shopify.csv
  uncertain.csv
  report.json
  report.md
  output.zip
```

---

### Task 1: Repo scaffold + CI + detector dependency

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/checker/__init__.py`, `.github/workflows/ci.yml`
- Test: `tests/test_smoke.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_smoke.py
def test_detector_dependency_importable():
    import shopify_domain_detector as sdd
    assert hasattr(sdd, "classify_domains")

def test_checker_package_imports():
    import checker
    assert checker.__version__
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: FAIL — detector + `checker` not installed.

- [ ] **Step 3: Write minimal implementation**

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "shopify-checker"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "shopify-domain-detector @ git+https://github.com/ahmedxomar101/shopify-domain-detector@v0.1.0",
  "supabase>=2.4",
]

[project.optional-dependencies]
dev = ["pytest>=8", "ruff>=0.6"]

[tool.hatch.build.targets.wheel]
packages = ["src/checker"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

```python
# src/checker/__init__.py
__version__ = "0.1.0"
```

```
# .gitignore
__pycache__/
*.pyc
.venv/
.pytest_cache/
.ruff_cache/
*.egg-info/
/tmp_jobs/
```

```yaml
# .github/workflows/ci.yml
name: CI
on:
  push: { branches: [main] }
  pull_request: { branches: [main] }
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: python -m pytest -v
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pip install -e ".[dev]" && python -m pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git init && git add -A
git commit -m "chore: scaffold shopify-checker worker + CI + detector dep"
```

---

### Task 2: Output bucketing (pure)

**Files:**
- Create: `src/checker/buckets.py`
- Test: `tests/test_buckets.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_buckets.py
from shopify_domain_detector.models import Category
from checker.buckets import bucket_of, Bucket

def test_shopify_bucket():
    for c in (Category.CONFIRMED_SHOPIFY, Category.SHOPIFY_IN_HTML_ACTIVE,
              Category.REDIRECTS_TO_SHOPIFY):
        assert bucket_of(c) == Bucket.SHOPIFY

def test_uncertain_bucket():
    for c in (Category.BOT_PROTECTED, Category.DEAD, Category.RATE_LIMITED,
              Category.SHOPIFY_IN_HTML_SUSPENDED):
        assert bucket_of(c) == Bucket.UNCERTAIN

def test_not_shopify_bucket():
    assert bucket_of(Category.NOT_SHOPIFY) == Bucket.NOT_SHOPIFY
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_buckets.py -v`
Expected: FAIL — `ModuleNotFoundError: checker.buckets`

- [ ] **Step 3: Write minimal implementation**

```python
# src/checker/buckets.py
from __future__ import annotations

from enum import Enum

from shopify_domain_detector.models import Category


class Bucket(str, Enum):
    SHOPIFY = "shopify"
    NOT_SHOPIFY = "not-shopify"
    UNCERTAIN = "uncertain"


_SHOPIFY = {
    Category.CONFIRMED_SHOPIFY,
    Category.SHOPIFY_IN_HTML_ACTIVE,
    Category.REDIRECTS_TO_SHOPIFY,
}
_UNCERTAIN = {
    Category.BOT_PROTECTED,
    Category.DEAD,
    Category.RATE_LIMITED,
    Category.SHOPIFY_IN_HTML_SUSPENDED,
}


def bucket_of(category: Category) -> Bucket:
    if category in _SHOPIFY:
        return Bucket.SHOPIFY
    if category in _UNCERTAIN:
        return Bucket.UNCERTAIN
    return Bucket.NOT_SHOPIFY
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_buckets.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/checker/buckets.py tests/test_buckets.py
git commit -m "feat: Category -> output Bucket mapping"
```

---

### Task 3: Job core — CSV in → 3 CSVs + report + zip

**Files:**
- Create: `src/checker/job.py`
- Test: `tests/test_job.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_job.py
import csv
import json
import zipfile
from unittest.mock import patch
from shopify_domain_detector.models import Category, DomainResult
from checker import job

def _write_csv(path, rows, header):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)

def test_run_job_splits_rows_and_writes_outputs(tmp_path):
    src = tmp_path / "input.csv"
    _write_csv(
        src,
        [["Gym", "gymshark.com"], ["Apple", "apple.com"], ["Dup", "gymshark.com"]],
        ["name", "website"],
    )
    fake = {
        "gymshark.com": DomainResult("gymshark.com", Category.CONFIRMED_SHOPIFY),
        "apple.com": DomainResult("apple.com", Category.NOT_SHOPIFY, platform="other"),
    }
    out = tmp_path / "out"
    with patch.object(job, "classify_domains", return_value=fake) as m:
        summary = job.run_job(str(src), domain_column="website", out_dir=str(out))
        # deduped: only 2 unique domains scraped, not 3
        assert sorted(m.call_args[0][0]) == ["apple.com", "gymshark.com"]

    shop = list(csv.DictReader(open(out / "shopify.csv")))
    notshop = list(csv.DictReader(open(out / "not-shopify.csv")))
    # both gymshark rows (incl. the duplicate) land in shopify.csv
    assert len(shop) == 2 and all(r["website"] == "gymshark.com" for r in shop)
    assert len(notshop) == 1 and notshop[0]["website"] == "apple.com"
    # original columns preserved + enrichment columns added
    assert shop[0]["name"] == "Gym"
    assert shop[0]["shopify_status"] == "confirmed-shopify"
    assert shop[0]["is_shopify"] == "true"

    report = json.load(open(out / "report.json"))
    assert report["total_rows"] == 3
    assert report["unique_domains"] == 2
    assert report["buckets"]["shopify"] == 2
    assert report["buckets"]["not-shopify"] == 1

    assert (out / "output.zip").exists()
    with zipfile.ZipFile(out / "output.zip") as z:
        names = set(z.namelist())
    assert {"shopify.csv", "not-shopify.csv", "uncertain.csv", "report.json"} <= names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_job.py -v`
Expected: FAIL — `ModuleNotFoundError: checker.job`

- [ ] **Step 3: Write minimal implementation**

```python
# src/checker/job.py
from __future__ import annotations

import csv
import json
import os
import zipfile

from shopify_domain_detector import classify_domains
from shopify_domain_detector.domains import normalize

from .buckets import Bucket, bucket_of

_EXTRA_COLUMNS = ["is_shopify", "shopify_status", "redirects_to"]


def _read_rows(path: str) -> tuple[list[str], list[dict]]:
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def _unique_domains(rows: list[dict], column: str) -> list[str]:
    seen = set()
    for r in rows:
        raw = (r.get(column) or "").strip()
        if raw:
            seen.add(normalize(raw))
    return sorted(seen)


def _write_csv(path: str, fieldnames: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def run_job(
    input_csv: str,
    domain_column: str,
    out_dir: str,
    workers: int = 50,
    progress=None,
) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    fieldnames, rows = _read_rows(input_csv)
    domains = _unique_domains(rows, domain_column)

    results = classify_domains(domains, workers=workers)
    if progress:
        progress(80)

    out_fields = fieldnames + _EXTRA_COLUMNS
    by_bucket: dict[Bucket, list[dict]] = {b: [] for b in Bucket}

    for r in rows:
        d = normalize((r.get(domain_column) or "").strip())
        res = results.get(d)
        if res is None:
            enriched = {**r, "is_shopify": "", "shopify_status": "", "redirects_to": ""}
            by_bucket[Bucket.UNCERTAIN].append(enriched)
            continue
        bucket = bucket_of(res.category)
        enriched = {
            **r,
            "is_shopify": "true" if res.is_shopify else "false",
            "shopify_status": res.category.value,
            "redirects_to": res.redirects_to or "",
        }
        by_bucket[bucket].append(enriched)

    _write_csv(os.path.join(out_dir, "shopify.csv"), out_fields, by_bucket[Bucket.SHOPIFY])
    _write_csv(os.path.join(out_dir, "not-shopify.csv"), out_fields, by_bucket[Bucket.NOT_SHOPIFY])
    _write_csv(os.path.join(out_dir, "uncertain.csv"), out_fields, by_bucket[Bucket.UNCERTAIN])

    cat_counts: dict[str, int] = {}
    for res in results.values():
        cat_counts[res.category.value] = cat_counts.get(res.category.value, 0) + 1

    report = {
        "total_rows": len(rows),
        "unique_domains": len(domains),
        "buckets": {b.value: len(by_bucket[b]) for b in Bucket},
        "categories": cat_counts,
    }
    with open(os.path.join(out_dir, "report.json"), "w") as f:
        json.dump(report, f, indent=2)
    with open(os.path.join(out_dir, "report.md"), "w") as f:
        f.write(_render_report_md(report))

    zip_path = os.path.join(out_dir, "output.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name in ("shopify.csv", "not-shopify.csv", "uncertain.csv",
                     "report.json", "report.md"):
            z.write(os.path.join(out_dir, name), name)

    if progress:
        progress(100)
    return report


def _render_report_md(report: dict) -> str:
    lines = [
        "# Shopify Lead Check",
        "",
        f"- Total rows: {report['total_rows']}",
        f"- Unique domains: {report['unique_domains']}",
        "",
        "| Bucket | Rows |",
        "|--------|------|",
    ]
    for b, n in report["buckets"].items():
        lines.append(f"| {b} | {n} |")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_job.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/checker/job.py tests/test_job.py
git commit -m "feat: job core — dedupe, classify, split rows, report + zip"
```

---

### Task 4: Supabase Storage I/O + status updates

**Files:**
- Create: `src/checker/storage.py`
- Test: `tests/test_storage.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storage.py
import json
from unittest.mock import MagicMock
from checker import storage

def test_set_status_uploads_json():
    client = MagicMock()
    s = storage.JobStore(client, bucket="shopify-checks")
    s.set_status("job123", state="running", progress=40)
    args, kwargs = client.storage.from_().upload.call_args
    # path includes the job folder + status.json
    assert "job123/status.json" in args[0]
    payload = json.loads(args[1])
    assert payload["state"] == "running" and payload["progress"] == 40

def test_download_input_returns_path(tmp_path):
    client = MagicMock()
    client.storage.from_().download.return_value = b"name,website\nx,x.com\n"
    s = storage.JobStore(client, bucket="shopify-checks")
    p = s.download_input("job123", dest_dir=str(tmp_path))
    assert open(p).read().startswith("name,website")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_storage.py -v`
Expected: FAIL — `ModuleNotFoundError: checker.storage`

- [ ] **Step 3: Write minimal implementation**

```python
# src/checker/storage.py
from __future__ import annotations

import json
import os


class JobStore:
    """Thin wrapper over Supabase Storage for one bucket of jobs."""

    def __init__(self, client, bucket: str = "shopify-checks"):
        self._client = client
        self._bucket = bucket

    def _b(self):
        return self._client.storage.from_(self._bucket)

    def set_status(self, job_id: str, *, state: str, progress: int = 0,
                   error: str | None = None) -> None:
        payload = json.dumps(
            {"state": state, "progress": progress, "error": error}
        )
        self._b().upload(
            f"{job_id}/status.json",
            payload.encode("utf-8"),
            {"content-type": "application/json", "upsert": "true"},
        )

    def read_meta(self, job_id: str) -> dict:
        raw = self._b().download(f"{job_id}/meta.json")
        return json.loads(raw)

    def download_input(self, job_id: str, dest_dir: str) -> str:
        raw = self._b().download(f"{job_id}/input.csv")
        os.makedirs(dest_dir, exist_ok=True)
        path = os.path.join(dest_dir, "input.csv")
        with open(path, "wb") as f:
            f.write(raw)
        return path

    def upload_outputs(self, job_id: str, out_dir: str) -> None:
        for name in os.listdir(out_dir):
            with open(os.path.join(out_dir, name), "rb") as f:
                self._b().upload(
                    f"{job_id}/{name}", f.read(), {"upsert": "true"}
                )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_storage.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/checker/storage.py tests/test_storage.py
git commit -m "feat: Supabase Storage job I/O + status updates"
```

---

### Task 5: Worker entrypoint

**Files:**
- Create: `src/checker/run.py`
- Test: covered by manual `workflow_dispatch` in Task 7 (entrypoint is glue).

- [ ] **Step 1: Write the entrypoint**

```python
# src/checker/run.py
from __future__ import annotations

import os
import sys
import tempfile

from supabase import create_client

from .job import run_job
from .storage import JobStore


def main(job_id: str) -> int:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    store = JobStore(create_client(url, key))

    try:
        store.set_status(job_id, state="running", progress=5)
        meta = store.read_meta(job_id)
        column = meta["domain_column"]
        with tempfile.TemporaryDirectory() as tmp:
            in_csv = store.download_input(job_id, tmp)
            out_dir = os.path.join(tmp, "out")
            run_job(
                in_csv, domain_column=column, out_dir=out_dir,
                progress=lambda p: store.set_status(job_id, state="running", progress=p),
            )
            store.upload_outputs(job_id, out_dir)
        store.set_status(job_id, state="done", progress=100)
        return 0
    except Exception as e:  # noqa: BLE001 — surface any failure to the UI
        store.set_status(job_id, state="failed", error=str(e))
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
```

- [ ] **Step 2: Lint**

Run: `ruff check src/checker/run.py`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add src/checker/run.py
git commit -m "feat: worker entrypoint (status lifecycle + run + upload)"
```

---

### Task 6: GitHub Actions worker workflow

**Files:**
- Create: `.github/workflows/run-check.yml`

- [ ] **Step 1: Write the workflow**

```yaml
# .github/workflows/run-check.yml
name: Run Shopify Check
on:
  repository_dispatch:
    types: [shopify-check]
  workflow_dispatch:
    inputs:
      job_id: { description: "Job ID", required: true }
concurrency:
  group: shopify-checker
  cancel-in-progress: false
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e .
      - name: Run job
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          JOB_ID: ${{ github.event.client_payload.job_id || github.event.inputs.job_id }}
        run: python -m checker.run "$JOB_ID"
```

- [ ] **Step 2: Configure repo secrets** (GitHub UI → Settings → Secrets):
  `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.

- [ ] **Step 3: Manual smoke** — upload a tiny `input.csv` + `meta.json` to a test
  `shopify-checks/manual-1/` folder (Supabase dashboard), then:

Run: `gh workflow run run-check.yml -f job_id=manual-1 --repo NavonaAI/shopify-checker`
Expected: workflow succeeds; `shopify-checks/manual-1/status.json` becomes
`done`; `shopify.csv`/`not-shopify.csv`/`uncertain.csv` appear.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/run-check.yml
git commit -m "ci: repository_dispatch worker for shopify checks"
```

---

### Task 7: Supabase bucket + RLS + CORS

**Files:**
- Create: `supabase/policies.sql` (documentation of applied policies)

- [ ] **Step 1: Create the bucket** (Supabase dashboard → Storage):
  - Name `shopify-checks`, **private**.

- [ ] **Step 2: Apply storage policies** (SQL editor) and save them to
  `supabase/policies.sql`:

```sql
-- supabase/policies.sql
-- Anon (browser) may upload inputs and read status/outputs within the bucket.
-- Tighten later (e.g. per-job signed paths) if needed; gated by app password.
create policy "anon read shopify-checks"
on storage.objects for select
to anon using (bucket_id = 'shopify-checks');

create policy "anon write shopify-checks inputs"
on storage.objects for insert
to anon with check (bucket_id = 'shopify-checks');
```

- [ ] **Step 3: Configure CORS** (Storage settings) to allow the GitHub Pages
  origin: `https://ahmedxomar101.github.io` (or the org Pages origin in use).

- [ ] **Step 4: Verify** — from a browser console on the Pages origin,
  `supabase.storage.from('shopify-checks').upload('probe/x.txt', new Blob(['hi']))`
  succeeds, and a cross-origin download of it succeeds.

- [ ] **Step 5: Commit**

```bash
git add supabase/policies.sql
git commit -m "infra: document Supabase bucket policies for shopify-checks"
```

---

### Task 8: Supabase Edge Function `enqueue` (push trigger)

**Files:**
- Create: `supabase/functions/enqueue/index.ts`

- [ ] **Step 1: Write the function**

```typescript
// supabase/functions/enqueue/index.ts
// Holds GH_DISPATCH_TOKEN server-side; fires repository_dispatch.
import { serve } from "https://deno.land/std@0.224.0/http/server.ts";

const GH_TOKEN = Deno.env.get("GH_DISPATCH_TOKEN")!;
const REPO = "NavonaAI/shopify-checker";
const ALLOW_ORIGIN = Deno.env.get("ALLOW_ORIGIN") ?? "*";

const cors = {
  "Access-Control-Allow-Origin": ALLOW_ORIGIN,
  "Access-Control-Allow-Headers": "content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") {
    return new Response("method not allowed", { status: 405, headers: cors });
  }
  const { jobId } = await req.json().catch(() => ({ jobId: null }));
  if (!jobId || !/^[a-zA-Z0-9_-]{6,64}$/.test(jobId)) {
    return new Response("bad jobId", { status: 400, headers: cors });
  }
  const res = await fetch(`https://api.github.com/repos/${REPO}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${GH_TOKEN}`,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      event_type: "shopify-check",
      client_payload: { job_id: jobId },
    }),
  });
  if (!res.ok) {
    return new Response(`dispatch failed: ${res.status}`, { status: 502, headers: cors });
  }
  return new Response(JSON.stringify({ ok: true }), {
    headers: { ...cors, "Content-Type": "application/json" },
  });
});
```

- [ ] **Step 2: Set the secret + deploy**

Run:
```bash
supabase secrets set GH_DISPATCH_TOKEN=<fine-grained PAT: actions:write on NavonaAI/shopify-checker only>
supabase secrets set ALLOW_ORIGIN=https://ahmedxomar101.github.io
supabase functions deploy enqueue
```

- [ ] **Step 3: Verify** — `curl -X POST <function-url> -d '{"jobId":"manual-1"}'`
  triggers a `repository_dispatch` run in Actions.

- [ ] **Step 4: Commit**

```bash
git add supabase/functions/enqueue/index.ts
git commit -m "feat: enqueue Edge Function — repository_dispatch push trigger"
```

---

### Task 9: Static HTML UI (GitHub Pages, password-gated, SRI-pinned)

**Files:**
- Create: `web/index.html`

- [ ] **Step 1: Write the page.** Required behaviors and hard rules:
  - **Password gate:** prompt; compare `sha256(input)` to a hardcoded hash; only
    reveal the app on match. (Soft gate; real protection is bucket RLS.)
  - **CDN scripts MUST use SRI** — PapaParse + supabase-js loaded with
    `integrity="sha384-..." crossorigin="anonymous"` (compute the hashes when
    pinning exact versions).
  - **Flow:** drag-drop CSV → `Papa.parse` headers → populate a `<select>` of
    columns → on **Check**:
    1. `jobId = crypto.randomUUID()`
    2. `supabase.storage.from('shopify-checks').upload(jobId+'/input.csv', file)`
    3. upload `meta.json` `{domain_column, rows, created_at}`
    4. upload `status.json` `{state:'queued', progress:0}`
    5. `POST` the Edge Function `{jobId}`
    6. navigate to `?job=<jobId>`
  - **Status view (`?job=` present):** poll `status.json` every 20s; render a
    progress bar; on `done`, render signed-URL download links for `shopify.csv`,
    `not-shopify.csv`, `uncertain.csv`, `report.json`, `output.zip`; on `failed`,
    show the error.
  - **Config:** `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `ENQUEUE_URL` as consts at
    top (anon key is public-safe behind RLS + password).

- [ ] **Step 2: Local check** — open `web/index.html`, confirm the password gate
  blocks, the column dropdown populates from a sample CSV, and the SRI attributes
  are present on both script tags.

Run: `python -c "t=open('web/index.html').read(); assert t.count('integrity=\"sha384-')>=2; assert 'status.json' in t; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Enable GitHub Pages** (Settings → Pages → deploy from `main`,
  `/web` folder or a `gh-pages` branch). Note the URL.

- [ ] **Step 4: Commit**

```bash
git add web/index.html
git commit -m "feat: static checker UI — password gate, SRI CDN, upload+poll"
```

---

### Task 10: End-to-end smoke + README/AGENTS

**Files:**
- Create: `README.md`, `AGENTS.md`

- [ ] **Step 1: E2E** — open the Pages link, enter the password, upload a 20-row
  CSV with a mix of Shopify and non-Shopify domains, pick the column, **Check**.
  Confirm: job page shows progress → `done`; downloaded `shopify.csv` contains the
  Shopify rows with all original columns + `is_shopify=true`; `report.json`
  bucket counts add up to row count.

- [ ] **Step 2: Write README.md** — what it is, the colleague flow (link +
  password → upload → pick column → download), the architecture diagram (reuse the
  epic mermaid), required secrets, and how to run the worker locally
  (`python -m checker.run <jobId>` with env vars).

- [ ] **Step 3: Write AGENTS.md** — module map (`buckets`/`job` pure-ish,
  `storage`/`run` I/O), golden rules (no secrets in `web/`; SRI on all CDN
  scripts; bucket access only via `JobStore`; detector pinned by tag — bump
  deliberately), test/lint commands, and the job data contract.

- [ ] **Step 4: Commit**

```bash
git add README.md AGENTS.md
git commit -m "docs: README + AGENTS for shopify-checker"
```

---

## Self-review notes
- Spec coverage: job ID + revisit (`?job=` Task 9); Supabase storage (Tasks 4,7);
  Edge Function push trigger (Task 8); all usual files + 3 CSVs individually +
  zip (Task 3); GH minutes safe via dispatch (Task 6); SRI per security hook
  (Task 9); password gate + RLS (Tasks 7,9).
- Type consistency: `Bucket`, `bucket_of`, `run_job(input_csv, domain_column,
  out_dir, workers, progress)`, `JobStore(client, bucket).{set_status,
  read_meta, download_input, upload_outputs}`, `checker.run.main(job_id)`,
  dispatch `event_type="shopify-check"` + `client_payload.job_id` used
  identically across worker, workflow, and Edge Function.
- No placeholders: code tasks contain complete content; infra tasks give exact
  config + verification commands.
