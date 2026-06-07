# smartlead-analytics → detector Migration Plan (Phase 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the inline classifier in `smartlead-analytics/analyze-shopify.py` with the `shopify-domain-detector` package so there's a single source of truth — with byte-identical output and zero impact on the daily KPI Sheet pipeline.

**Architecture:** `analyze-shopify.py` keeps its app-specific shell (SmartLead lead fetch, domain extraction, file/report writing, bounce analysis) but delegates all detection — cart.js probe, HTML probe, signatures, domain comparison, and categorization — to the package. Behavior is preserved by construction (the package was ported verbatim from this file) and locked by a truth-table parity test.

**Tech Stack:** Python 3, `shopify-domain-detector@v0.1.0` (new dependency), existing stdlib shell.

**Prerequisite:** Phase 1 tagged `v0.1.0`.

## Safety constraints (non-negotiable)

- **Branch only.** All work on `refactor/use-shopify-domain-detector` off `master`. Do **not** push to `master` until parity is proven and the PR is code-reviewed.
- **Daily pipeline is untouched.** `update-analytics.yml` runs `report-api.py save` + `export_sheets.py`; the Shopify step is commented out and `export_sheets.py` only *reads* `data/analytics/*/report.json`. This migration changes only the manually-run classifier. Confirm the workflow's pip step is **not** modified.
- **Merge gate:** truth-table parity green + one real-campaign `report.json` byte-identical to a pre-migration baseline + code review approved. Never merge with failing tests.

## File Structure

```
smartlead-analytics/
  analyze-shopify.py          # MODIFY: delegate detection to the package
  requirements-shopify.txt    # CREATE: pins the detector for manual runs
  tests/test_shopify_parity.py # CREATE: truth-table parity guard
  CLAUDE.md                   # MODIFY: note the new dependency
  docs/superpowers/plans/...  # this plan (copy on the branch)
```

---

### Task 0: Branch + capture baseline

- [ ] **Step 1: Create the feature branch**

Run:
```bash
cd smartlead-analytics
git checkout master && git pull
git checkout -b refactor/use-shopify-domain-detector
```

- [ ] **Step 2: Capture a pre-migration golden baseline** for a real campaign with
  existing committed data (e.g. 3324671):

Run:
```bash
cp data/analytics/campaign_3324671/report.json /tmp/baseline_3324671_report.json
```
Expected: file copied. This is the byte-identical target for Task 4.

- [ ] **Step 3: Commit the plan onto the branch**

```bash
git add docs/superpowers/plans/2026-06-07-analytics-detector-migration.md
git commit -m "docs: add detector migration plan"
```

---

### Task 1: Add the detector dependency (manual-run only)

**Files:**
- Create: `requirements-shopify.txt`

- [ ] **Step 1: Write the requirements file**

```
# requirements-shopify.txt
# Detection engine for analyze-shopify.py (manual/local runs only).
# NOT installed by the daily KPI workflow.
shopify-domain-detector @ git+https://github.com/ahmedxomar101/shopify-domain-detector@v0.1.0
```

- [ ] **Step 2: Install + verify import**

Run: `pip install -r requirements-shopify.txt && python -c "import shopify_domain_detector as s; print(s.__version__)"`
Expected: prints `0.1.0`.

- [ ] **Step 3: Confirm the daily workflow is unchanged**

Run: `git diff master -- .github/workflows/update-analytics.yml`
Expected: **no output** (workflow untouched).

- [ ] **Step 4: Commit**

```bash
git add requirements-shopify.txt
git commit -m "chore: pin shopify-domain-detector for manual shopify runs"
```

---

### Task 2: Truth-table parity guard (RED first)

**Files:**
- Create: `tests/test_shopify_parity.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_shopify_parity.py
"""The package's categorizer must match the categories analyze-shopify.py has
always produced. This is the migration contract."""
from shopify_domain_detector.models import Category, ProbeResult
from shopify_domain_detector.detector import categorize

# (status, platforms, suspended, rate_limited) -> legacy category file name
LEGACY_TRUTH = [
    ((429, ("shopify",), False, True), "rate-limited"),
    ((403, (), False, False), "bot-protected"),
    ((403, ("shopify",), False, False), "shopify-in-html-suspended"),
    ((200, ("shopify",), False, False), "shopify-in-html-active"),
    ((200, ("shopify",), True, False), "shopify-in-html-suspended"),
    ((404, ("shopify",), False, False), "shopify-in-html-suspended"),
    (("unreachable", (), False, False), "dead"),
    ((200, ("squarespace",), False, False), "not-shopify"),
    ((200, (), False, False), "not-shopify"),
]

def test_package_categories_match_legacy_filenames():
    for (status, platforms, suspended, rl), expected in LEGACY_TRUTH:
        probe = ProbeResult(
            domain="x.com", status=status, platforms=platforms,
            suspended_shopify=suspended, rate_limited=rl,
        )
        cat, _ = categorize(probe)
        assert cat.value == expected
```

- [ ] **Step 2: Run test**

Run: `python -m pytest tests/test_shopify_parity.py -v`
Expected: PASS (package already matches). If it FAILS, the package drifted — fix the package, not this test.

- [ ] **Step 3: Commit**

```bash
git add tests/test_shopify_parity.py
git commit -m "test: lock package categorizer to legacy analyze-shopify categories"
```

---

### Task 3: Delegate detection to the package

**Files:**
- Modify: `analyze-shopify.py`

The app shell stays: `fetch_leads`, `extract_domains`, `write_list`,
`_analyze_bounces`, `run`'s file/report writing, `main`. Replace the detection
internals with package calls.

- [ ] **Step 1: Replace the detection imports + helpers.** At the top of
  `analyze-shopify.py`, after the stdlib imports, add:

```python
from shopify_domain_detector import classify_domains as _pkg_classify_domains
from shopify_domain_detector.domains import is_same_domain as _is_same_domain
from shopify_domain_detector.models import Category
```

- [ ] **Step 2: Delete the now-duplicated internals** from `analyze-shopify.py`:
  `PLATFORM_SIGNATURES`, `SHOPIFY_SUSPENDED_TITLE`, `_ssl_ctx`, `_make_request`,
  `_is_cart_js_shopify`, `_detect_platforms`, `_is_suspended_shopify`,
  `_probe_domain`, `_base_domain`, `_is_same_domain` (now imported),
  `check_shopify`. Keep `_resolve_dns` (DNS phase is app-specific reporting).

- [ ] **Step 3: Replace the body of `run()`'s phases 1–4** with a single call to
  the package, then bucket the package categories into the legacy file lists.
  Replace everything from the `# Phase 1` comment down to the
  `shopify_html_active.sort()` block with:

```python
    # Detection delegated to shopify-domain-detector (single source of truth).
    print(f"\n[1/2] Classifying {len(domains)} domains...")
    results = _pkg_classify_domains(domains, workers)

    confirmed_direct = []
    redirects_to_shopify = []
    shopify_html_active = []
    shopify_html_suspended = []
    not_shopify = []
    dead = []
    rate_limited = []
    bot_protected = []

    for domain in sorted(domains):
        r = results.get(domain)
        if r is None:
            dead.append(domain)
            continue
        cat = r.category
        if cat == Category.CONFIRMED_SHOPIFY:
            confirmed_direct.append(domain)
        elif cat == Category.REDIRECTS_TO_SHOPIFY:
            redirects_to_shopify.append((domain, r.redirects_to or ""))
        elif cat == Category.SHOPIFY_IN_HTML_ACTIVE:
            shopify_html_active.append(domain)
        elif cat == Category.SHOPIFY_IN_HTML_SUSPENDED:
            shopify_html_suspended.append(domain)
        elif cat == Category.DEAD:
            dead.append(domain)
        elif cat == Category.RATE_LIMITED:
            rate_limited.append(domain)
        elif cat == Category.BOT_PROTECTED:
            bot_protected.append(domain)
        else:  # NOT_SHOPIFY
            not_shopify.append((domain, r.platform or ""))

    print(f"  cart.js/HTML confirmed: {len(confirmed_direct)}")

    confirmed_direct.sort()
    redirects_to_shopify.sort()
    shopify_html_active.sort()
    shopify_html_suspended.sort()
    dead.sort()
    rate_limited.sort()
    bot_protected.sort()
    not_shopify.sort()
```

  Leave the existing `# Export`, report-building, bounce-analysis, and
  `report.json`/`report.md` writing code **exactly as is** — it consumes the same
  eight lists and produces the same files.

- [ ] **Step 4: Remove now-unused imports** (`ssl`, `concurrent.futures`,
  `urllib.request` if no longer referenced) and run the linter.

Run: `ruff check analyze-shopify.py` (or `python -m pyflakes analyze-shopify.py`)
Expected: no unused-import or undefined-name errors.

- [ ] **Step 5: Commit**

```bash
git add analyze-shopify.py
git commit -m "refactor: delegate shopify detection to shopify-domain-detector"
```

---

### Task 4: Live E2E parity on a real campaign

- [ ] **Step 1: Re-run the classifier on the baseline campaign**

Run: `python analyze-shopify.py --from-json campaigns_raw/campaign_3324671.json`
Expected: completes; writes `data/analytics/campaign_3324671/` files.

- [ ] **Step 2: Diff report.json against the baseline.** Counts must match
  (network noise can shift at most a handful of bot-protected/dead — investigate
  any larger delta before proceeding):

Run:
```bash
python3 -c "
import json
old = json.load(open('/tmp/baseline_3324671_report.json'))
new = json.load(open('data/analytics/campaign_3324671/report.json'))
keys = ['total','confirmed_shopify','shopify_in_html_active','shopify_suspended',
        'redirects_to_shopify','not_shopify','dead','rate_limited','bot_protected']
for k in keys:
    flag = 'OK' if old.get(k)==new.get(k) else 'DIFF'
    print(f'{flag:4} {k}: {old.get(k)} -> {new.get(k)}')
"
```
Expected: all `OK`, or only ±small movement on `bot_protected`/`dead` explained by
live network variance (matches the Phase-0 verification finding).

- [ ] **Step 3: Confirm all eight category files still written**

Run: `ls data/analytics/campaign_3324671/{confirmed-shopify,shopify-in-html-active,shopify-in-html-suspended,redirects-to-shopify,not-shopify,dead,rate-limited,bot-protected}.txt`
Expected: all eight exist.

- [ ] **Step 4: Run the unit suite**

Run: `python -m pytest tests/test_shopify_parity.py -v`
Expected: PASS.

---

### Task 5: Docs + PR + review + merge

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md.** Change the "no external dependencies (stdlib
  only)" line for analyze-shopify to note it now depends on
  `shopify-domain-detector` (install via `requirements-shopify.txt`), and that the
  detection logic's single source of truth is that package.

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: note shopify-domain-detector dependency for analyze-shopify"
```

- [ ] **Step 3: Push + open PR against `master`**

Run:
```bash
git push -u origin refactor/use-shopify-domain-detector
gh pr create --base master --title "refactor: single source of truth for Shopify detection" \
  --body "Delegates analyze-shopify.py detection to shopify-domain-detector@v0.1.0. Daily KPI pipeline untouched (Shopify step disabled in CI). Parity: truth-table test green; campaign 3324671 report.json matches baseline."
```

- [ ] **Step 4: Code review (REQUIRED — no merge without it).**
  Skill: `code-review:code-review`. Two-stage: spec compliance (matches this
  plan?) then quality (unused code removed, lint clean, no behavior change).
  Address feedback via `superpowers:receiving-code-review`.

- [ ] **Step 5: Merge only after review approves + tests green.** Squash-merge,
  delete branch:

Run: `gh pr merge --squash --delete-branch`
Expected: merged to `master`. The daily pipeline behaves identically (it never
called the classifier).

---

## Self-review notes
- Spec coverage: single source of truth (Tasks 1,3); no pipeline breakage
  (Safety constraints + Task 1 Step 3 + Task 5 Step 5); parity (Tasks 2,4);
  branch + review workflow (Tasks 0,5) per DEVELOPMENT_PROCESS.md.
- Type consistency: uses package `Category` enum values + `DomainResult.platform`
  / `.redirects_to` exactly as defined in Phase 1; legacy eight-list/file names
  unchanged so the existing report writer is untouched.
- No placeholders: refactor steps name exact symbols to delete and show the exact
  replacement block; verification steps are runnable commands with expected output.
