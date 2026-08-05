# Launch checklist

## Phase 1 — Concept review

- Run demo mode with member and admin personas.
- Validate terminology with AIA Canada research, membership and communications teams.
- Confirm that the 2015 metrics were transcribed correctly against source pages 7–10, 12 and 15.
- Agree on the first current dataset that will replace or supplement the historical benchmark.
- Approve the contribution template and identify fields that need methodology notes.

## Phase 2 — Connected pilot

- Apply the Supabase migration in a non-production project first.
- Seed data and run the member/admin smoke test.
- Invite a small pilot group; keep public signup disabled.
- Require a data-sharing agreement and document withdrawal/retention handling.
- Set cohort suppression thresholds before any member-derived aggregate is published.
- Confirm English/French content and accessibility requirements.

## Phase 3 — Production

- Enable admin MFA and restrict administrator assignment to a controlled process.
- Configure a custom domain, support address and incident owner.
- Add password recovery and branded email templates.
- Add malware/content scanning for contribution files.
- Add monitoring for failed logins, repeated upload failures and admin lifecycle changes.
- Back up the database and test restoration.
- Complete privacy, legal and security review.
- Publish a data release calendar and methodology/version policy.

## Smoke test

1. Pending user can sign in but cannot open portal data.
2. Admin can activate that profile; user can sign in again and access published data.
3. Active member cannot read draft or archived datasets/resources.
4. Active member can upload only CSV/XLSX to their own contribution folder.
5. Active member cannot read another member’s contribution metadata or file.
6. Admin can review all submissions and set status.
7. Approval does not make a raw file visible to members.
8. Member cannot stage datasets or publish CMS resources.
9. Admin can stage a CSV as draft and archive a dataset.
10. CSV, XLSX and PDF exports include source context and the historical-data warning.
