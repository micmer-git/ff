# Weekly selected material → FF Substack draft

## Setup on any machine

1. Clone `https://github.com/micmer-git/ff.git` and read `AGENTS.md`.
2. Use a browser/computer-use tool and sign in to Discord and Substack normally.
   Never transfer cookies or tokens through Git. Login, CAPTCHA or access failure
   requires user handoff; it does not justify bypassing the service.
3. Copy `editorial/config.example.json` to `editorial/local/config.json`, replacing
   the channel and actor with those confirmed by the user. The public example
   deliberately contains no private server identifiers.
4. Run `python scripts/ff_weekly.py init --week YYYY-Www` from the repository root.
5. Install the weekly prompt below in the agent scheduler on the new machine.
   A Git clone does not install a scheduler or carry authenticated browser access.
   Keep exactly one active scheduler owner. Transfer the private local manifest
   through an approved private channel, or reconstruct it from Substack before
   creating anything. Do not enable two machines to create the same week's issue.

## Intake and parsing

Read only configured channels and the user-selected material. On a dedicated
OpenClaw intake channel, links, text and images shared by the confirmed user are
candidates, not mandatory inclusions. Other authors or other servers require an
explicit selection rule. Do not infer selection from other people's reactions.
Use Discord UI as requested; do not scrape tokens or install a self-bot.

On first setup, inventory a bounded historical window and label it backlog. On
weekly runs, inspect new messages since the last completed intake checkpoint,
with an overlap to catch edits and late attachments. Discord virtualizes history:
scroll and record actual date coverage; an initial view is not a complete export.
Advance the checkpoint only after the parsed records are saved. Never mark unseen
history as processed. Retain unused backlog and record exclusions with reasons.

For each candidate record: stable message ID/permalink, author, shared date,
original URL, concise paraphrase of the user context, attachment description,
original publication date, original-source reading status, facts to check,
editorial angle, and inclusion decision. Save to `editorial/local/inbox.json`.
Open linked articles, follow useful original-source citations, and inspect images
visually. OCR is provisional until compared with the image. Keep excerpts brief.
Paywalls, deleted posts and login walls are explicit blockers, not read articles.
Preserve semantic URL parameters; strip only known tracking parameters for dedup.

## Editorial assembly

Read `STYLE.md` and recent published issues. Compare candidates with the archive
and ALL existing drafts, including drafts made manually. Select the strongest
coherent angle; preserve unused material for later. Old shares may be used as
dated context, never passed off as this week's news. No arbitrary minimum forces
an issue: when material is insufficient, record `no_material` and skip creation.

Create `editorial/local/issues/YYYY-Www/body.md`, `metadata.json`, `sources.json`
and `images.json`. Record verified claims with supporting URLs and access dates;
include uncertainty and source disagreements. Record image provenance, caption,
alt text, reuse basis and actual placement. Update `manifest.json` throughout.

## Substack save and recovery

Verify the signed-in publication and open its Drafts list. Reconcile by manifest
draft URL, title and source set BEFORE creating. If a matching draft exists,
resume it, preserving human changes. If there is ambiguity, stop duplicate creation
and report the candidates. Record the draft URL as soon as creation returns it.
Before a browser mutation record `save_pending`; after an uncertain outcome inspect
the Drafts list and reopen the candidate rather than blindly retrying creation.

Insert body, links and approved images using supported editor UI. Save title,
subtitle and available metadata. Inspect preview and verify the saved indicator.
Reload/reopen and compare body, intended links, figures and metadata. Only then
record `saved_unpublished`, source IDs used and verification time. If a metadata
field is not exposed, record it pending rather than claiming it was saved.
Never press Publish or schedule publication. Do not email or post to Discord.

## Weekly scheduler prompt (portable)

Every Friday at 09:00 in the scheduler's local timezone, continue the FF weekly
workflow in this task. Current installation: Asia/Shanghai. On another machine,
verify the scheduler timezone explicitly; use Europe/Rome for ISO issue weeks.
Resolve the configured repository checkout; read AGENTS.md, editorial/STYLE.md,
editorial/WEEKLY_WORKFLOW.md and private local config/issue manifests. Verify
Discord and Substack access. Through computer use, read new user-selected shares
in the configured channel, parse articles and screenshots, verify original
sources, deduplicate against saved sources, published issues and existing drafts.
Choose a coherent FF angle, prepare Italian copy and metadata, include useful
credited images where appropriate, and save one unpublished Substack draft for
the Europe/Rome ISO week. Reopen and verify persistence; record its URL and source
IDs. If access fails, preserve local work and report the exact required action.
If there is no adequate new material, do not fabricate a draft. Stay quiet on
unchanged or non-actionable state; notify for a new verified draft, meaningful
failure, or required user action. Never publish, schedule, email, or send Discord
messages. Reconcile uncertain saves before any retry. A new machine must establish
its own authenticated session and scheduler ownership.

## Validation

`python -m unittest discover -s tests -p 'test_ff_weekly.py'`

The helper only initializes and deduplicates private intake files. The agent does
editorial judgment, source reading and browser saves; there is no unattended
Substack API integration hidden in this script.
