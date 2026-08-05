# AIA Canada Data Portal

A GitHub-ready conceptual application for a member-only auto care industry data hub. It combines Streamlit dashboards and report exports with Supabase Auth, Postgres, Row Level Security, private Storage, a member contribution workflow, and an administrator CMS.

The app runs immediately in demo mode and switches to production Supabase services when secrets are configured.

## What is included

- Member login and separate membership approval status
- Dashboard, regional benchmark explorer, cohort comparison and opportunity calculator
- CSV, Excel and PDF report exports
- Standardized CSV/XLSX shop-data contribution template
- Upload validation and PII-column rejection
- Private contribution storage and AIA Canada approval queue
- Admin member access, submission review, dataset staging/archive and resource CMS
- In-portal Markdown/sanitized-HTML articles and validated external HTTPS resources
- Secure administrator editing and permanent deletion of member accounts
- Supabase schema with explicit Data API grants, RLS policies and private Storage policies
- Page-level provenance for all values transcribed from the 2015 AIA Canada report
- Statistics Canada Census Profile integration for provinces, municipalities and three-character postal regions
- Database-filtered municipality/FSA search, linked AIA regional benchmarks and an explicit market-assumption scenario
- Governed benchmark ingestion with typed CSV templates, strict validation and manual row-entry drafts
- Demo member/admin workspaces for stakeholder review

## Local demo

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open the app and choose **View as member** or **View as admin**. No Supabase connection is required in demo mode.

## Connect the existing Supabase project

Requirements: Node/npm, Supabase project access, and the Supabase CLI.

1. Link and apply the database migration:

   ```bash
   npx supabase@2.111.0 login
   npx supabase@2.111.0 link --project-ref YOUR_PROJECT_REF
   npx supabase@2.111.0 db push
   ```

   Deploy the authenticated user-administration Edge Function:

   ```bash
   npx supabase@2.111.0 functions deploy admin-users
   ```

2. Create or invite the first administrator in **Supabase Dashboard → Authentication → Users**. Then run this once in the SQL Editor, using the administrator’s email:

   ```sql
   update public.profiles p
   set role = 'admin', membership_status = 'active'
   from auth.users u
   where p.id = u.id and u.email = 'ADMIN_EMAIL_HERE';
   ```

3. Seed the extracted historical benchmark rows from a trusted local terminal. Use a secret key only for this operator command:

   ```bash
   export SUPABASE_URL='https://YOUR_PROJECT_REF.supabase.co'
   export SUPABASE_SECRET_KEY='sb_secret_YOUR_KEY'
   python scripts/seed_data.py
   unset SUPABASE_SECRET_KEY
   ```

   Legacy projects can use `SUPABASE_SERVICE_ROLE_KEY` instead. Never add either secret to Streamlit.

4. Load official demographic snapshots after the demographic migration is applied:

   ```bash
   export SUPABASE_URL='https://YOUR_PROJECT_REF.supabase.co'
   export SUPABASE_SECRET_KEY='sb_secret_YOUR_KEY'
   python scripts/sync_statcan_demographics.py
   unset SUPABASE_SECRET_KEY
   ```

   The script reads the Statistics Canada 2021 Census Profile SDMX API and loads provinces/territories, census subdivisions (municipalities), and forward sortation areas (three-character postal regions). Run it only from a trusted operator terminal.

5. Confirm the first admin can sign in, then approve other member profiles from **Admin Centre → Users & access**.

Administrators can edit a member's email, profile, role and membership status from the same screen. Permanent deletion removes the Auth account, profile, private contribution records and contribution files. The current administrator and the last active administrator are protected from deletion.

Administrators add member resources from **Admin Centre → Content CMS**. Choose **In-portal article** for Markdown or sanitized HTML, or **External link** for a complete HTTPS URL. Drafts may be incomplete; publishing requires the selected destination to contain content or a valid link.

Administrators stage new benchmark source files from **Admin Centre → Datasets**. Choose the regional/shop-size or performance-cohort contract, download its CSV template, and upload the completed file. The same rules validate manual row entry. Valid drafts are normalized before private Storage upload; invalid columns, values, ranges, duplicates, slugs and formula-like text are rejected.

## Deploy on Streamlit Community Cloud

1. Push this directory to the GitHub repository and select `app.py` as the entrypoint in Streamlit.
2. In Streamlit app settings, add:

   ```toml
   SUPABASE_URL = "https://YOUR_PROJECT_REF.supabase.co"
   SUPABASE_PUBLISHABLE_KEY = "sb_publishable_YOUR_KEY"
   ENABLE_DEMO_MODE = "false"
   SUPPORT_EMAIL = "data@aiacanada.com"
   MAX_UPLOAD_MB = "10"
   ```

3. Deploy. The secret/service-role key must not be present.
4. Add the deployed Streamlit URL to the allowed redirect/site URLs in Supabase Auth if you later add password-reset, magic-link, OAuth or SSO flows.

## Repository map

| Path | Purpose |
|---|---|
| `app.py` | Streamlit member and admin interface |
| `src/aia_portal/` | Auth, data, exports, validation, repository and UI modules |
| `supabase/migrations/` | Database, RLS, Storage and initial CMS records |
| `scripts/seed_data.py` | Trusted operator seed loader |
| `scripts/sync_statcan_demographics.py` | Trusted Statistics Canada demographic synchronizer |
| `data/` | Source-transcribed benchmarks and member template |
| `data/*benchmark_upload_template.csv` | Governed administrator dataset templates |
| `docs/ARCHITECTURE.md` | Trust boundaries, roles and hardening backlog |
| `docs/DATA_DICTIONARY.md` | Benchmark and contribution field definitions |
| `docs/MARKET_LINKAGE.md` | Rules separating direct demographic/benchmark links from scenario assumptions |
| `.github/workflows/ci.yml` | Lint, test and compile checks |

## Data governance notes

- The included research is from 2015 and is always labelled as historical. It should not be presented as the current Canadian market.
- Member uploads are aggregate monthly shop data only. Direct customer, employee, vehicle and invoice identifiers are prohibited.
- “Approved” contributions remain private. AIA Canada must perform a separate aggregation/suppression process before publishing any derived dataset.
- Archive datasets instead of hard-deleting them unless a documented privacy or legal requirement requires deletion.

## Verification

```bash
pip install -r requirements-dev.txt
ruff check app.py src tests scripts
pytest -q
python -m compileall -q app.py src scripts
```

## Next product decisions

Before production launch, AIA Canada should confirm bilingual scope, data-sharing terms, minimum cohort suppression thresholds, retention rules, admin MFA, recovery flows, and whether shop users belong to organization-level accounts.
