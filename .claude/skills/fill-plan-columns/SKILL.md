---
name: fill-plan-columns
description: Fill and correct the production columns (Cue #, Audio, On Stage, Switcher, Timer) on the next two weekends of Northridge Rochester Campus plans in Planning Center Services, and match Rochester's song lengths to Central's. Use when asked to fill in, fix, check, or update the service order / plan details / cue numbers / mics / On Stage / song times for upcoming Rochester services, or when the weekly routine runs.
---

# Fill Rochester plan production columns

Rochester's weekend plans in Planning Center Services (one plan covers the Thursday 6:45 PM
service and the Sunday services, e.g. "October 22 & 25, 2026") carry custom item-note
columns that the production team runs from: **Cue #, Audio, On Stage, Switcher, Timer**.
Its song lengths should also match Central's. `scripts/fill_plan.py` applies the rules below
and writes them through the Planning Center API.

Always keep the **next two weekends** accurate (e.g. on Tue Oct 20: "October 22 & 25" and
"October 29 & November 1"). Never touch plans further out. Never touch the **Leader** column
or **song timers**.

## The rules

The script implements all of these. They're listed so you can sanity-check its output.

- **Cue #**: Pre-Service = 1, then +1 for every item in order. End of Service / Copyrights goes back to 1.
- **Pre-Service**: Audio Spotify, Switcher Mac. **Countdown**: Audio Mac, Switcher Mac. **End of Service**: Switcher Mac.
- **On Stage** is always first name + last initial (`Sam P.`, `Alex K.`) on every element.
  Shared leads are written `Jordan R. / Sam P.`.
- **Songs** (including Spiritual Direction and Flow): Audio = `W{n}/Band`, where n is the Music
  Team "Vocal n" position of the person in On Stage. Shared leads get one mic each: `W1/W5/Band`.
  On Stage is always a vocalist. Nicknames are matched to the roster ("Sam" → Samantha, "Liz" → Elizabeth)
  only when exactly one singer fits.
- **Host Moment**: Audio W8/Band, On Stage = the Speaking team's Host. **Closing Comments**: W8/Keys, Host.
  A Host Moment with several people on it is a deliberate one-off and is left alone (flagged).
- **Message** and **Transition Comments**: Audio W7, On Stage = that Sunday's speaker from the
  Preaching Calendar (the preacher gives the transition comments too).
- **Speaking moments** (Host Moment, Transition Comments, Message, Closing Comments): Timer = the item's length.
- **Live Baptism**: Audio W9.
- **Videos** (title contains video, promo, title package, or story — e.g. Story of Life Change): Audio Mac, Switcher Mac.
- **Switcher** only ever says `Mac` or is blank. Any other value (e.g. `Stream`) is cleared.
- Anything else with a blank Audio is **flagged as a question**, never guessed.
- Fill empty cells **and** fix cells that break these rules.

### Song lengths come from Central

Every **real song** in a Rochester plan (the ones brought in from the song rotation that week)
gets the same **Length** as that song in the **_CENTRAL** plan (service type `1755399`) for the
same Sunday. Songs are matched by their Planning Center song record, falling back to the title.

- **Not** length-matched: the recurring song-like elements: Spiritual Direction, Flow,
  Host Moment, Closing Comments (and anything starting with "Offering").
- If Central has no plan for that Sunday, or a Rochester song isn't in Central's plan, the
  length is left alone and flagged.
- Changing lengths moves the item start times in the plan. That's expected.
- Do the length matching **before** checking anything else that depends on length.

## Steps

1. **Credentials.** The script needs a Planning Center Personal Access Token in `PCO_APP_ID` /
   `PCO_SECRET`. If those aren't already in the environment, use the Google Drive connector:
   `search_files` for a doc titled **"Planning Center API Token (Claude — Private)"** in the user's
   own Drive, read it with `read_file_content`, and take the APP_ID / SECRET (also labelled
   Client ID / Secret). Export them in the same Bash command that runs the script. Never write
   them to a file and never repeat them in your summary.

2. **Preaching Calendar.** Use the Drive `search_files` tool to find the Google Sheet titled
   **"Preaching Calendar // Northridge Church"**, then call `download_file_content` with its
   fileId and exportMimeType `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. The result is too big for
   context and gets saved to a file — that's expected. Note the saved path; the script reads it
   directly (JSON/base64 wrapper or plain .xlsx) and takes each Sunday's speaker from column I of
   the "Preaching Calendar" tab.

3. **Dry run**:
   `python3 scripts/fill_plan.py --calendar <saved path>`
   (path relative to this skill's folder). It processes the next two weekend plans and prints
   every change it would make plus any flags. If anything looks clearly wrong — plans that aren't
   the next two weekends, or lots of existing values being wiped — stop and explain instead of applying.

4. **Apply**: the same command with `--apply`. Then dry-run once more and confirm both plans say
   "No changes needed".

5. **Report.** Per plan: the dates, what changed (item, column, old → new), and every flag as a
   plain-language question. When running unattended (scheduled routine), also send a
   PushNotification with a one-line summary.

If a Planning Center request fails with a connection/tunnel error rather than an HTTP status, the
environment can't reach `api.planningcenteronline.com` — say so plainly and stop.

## Useful flags

- `--plan <PLAN_ID>` — work on one specific plan instead of the next two.
- `--speaker <FirstName>` — override the speaker (with `--plan`).
- No `--calendar` — speakers come from the Service Planning page
  (nbantle.github.io/service-planning). That page isn't reachable from cloud routines.

## Known gaps

- A speaker who has never had a Message "On Stage" entry before (e.g. a first-time guest) can't be
  given a last initial automatically — it's flagged and On Stage is left blank.
- IDs in the script (`ST = '34139'` Rochester Campus, and the item-note category IDs in `CAT`) are
  specific to Northridge's Planning Center account.
