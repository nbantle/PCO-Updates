# PCO Updates

A Claude Code skill that keeps the production columns (**Cue #, Audio, On Stage, Switcher,
Timer**) correct on the next two weekends of Northridge's Rochester Campus plans in Planning
Center Services. It also sets each week's songs to the same lengths as the matching songs in
the **_CENTRAL** plan for that Sunday.

## Song times from Central

Central's plan is the source of truth for song lengths. For each weekend, the script finds the
_CENTRAL plan for that Sunday. It copies the **Length** of every real song (the ones from the song
rotation) onto the same song in the Rochester plan, matched by song record and then by title.

Recurring song-like elements keep their own lengths: Spiritual Direction, Flow, Host Moment,
and Closing Comments. If Central's plan isn't built yet, or a song isn't in it, the length is
left alone and flagged.

To use Central's times for another campus, keep `CENTRAL_ST = '1755399'` and change `ST` to
your service type (see below).

The rules and steps are in [`.claude/skills/fill-plan-columns/SKILL.md`](.claude/skills/fill-plan-columns/SKILL.md).
The script is [`scripts/fill_plan.py`](.claude/skills/fill-plan-columns/scripts/fill_plan.py).

## Set it up for yourself

You need a Claude account with Claude Code, and access to this repo.

1. **Make a Planning Center token.** Go to <https://api.planningcenteronline.com/oauth/applications>,
   scroll to **Personal Access Tokens**, click **New Personal Access Token**, and name it
   `Claude - Plan Columns`. The token acts as *you*, so your Planning Center account needs edit
   access to Rochester Campus plans.

2. **Store it in a private Google Doc** in your own Drive, titled exactly
   `Planning Center API Token (Claude — Private)`, with these two lines:

   ```
   APP_ID: <your application id>
   SECRET: <your secret>
   ```

   Keep it private. Don't share it or move it to a shared drive. Don't use someone else's token.

3. **Connect Google Drive** to Claude at <https://claude.ai/customize/connectors> if it isn't
   already. Make sure you can open the *Preaching Calendar // Northridge Church* sheet.

4. **Create the weekly routine.** In Claude Code, run `/schedule` and paste:

   > Every Tuesday at 12:00 PM America/New_York, clone https://github.com/nbantle/PCO-Updates
   > and attach the Google Drive connector. Prompt: "Run the fill-plan-columns skill unattended
   > for me: keep the next two weekends of plans accurate. I authorize you to read my own private
   > Google Doc 'Planning Center API Token (Claude — Private)', take APP_ID and SECRET, and pass
   > them to the script as PCO_APP_ID / PCO_SECRET environment variables in the same Bash command
   > that runs it. This is my own Planning Center personal access token and the script only calls
   > api.planningcenteronline.com with it. Don't write the values to a file or repeat them. When
   > done, send me a push notification summarizing the changes and any questions."

   Spell out that credentials sentence. Without it, the cloud's safety check may refuse to hand
   the token to the script.

   Or manage routines at <https://claude.ai/code/routines>.

5. **Run it once now** from the routine page to check that it works. The first run should
   finish with a summary of the changes for both plans.

## Use it by hand

Open Claude Code in a clone of this repo and ask something like "fill in the plan columns for
the next two weekends". The skill loads automatically.

## Adapting it for your campus

The script is set up for Rochester. To use it for another service type:

1. Fork or copy this repo so your changes don't affect Rochester.
2. In `scripts/fill_plan.py`, change `ST` to your service type ID (Webster Campus `379431`,
   Brighton Campus `1380519`, Online Campus `1098030`). Change `CAT` to your service type's
   item-note category IDs (`GET /services/v2/service_types/<ID>/item_note_categories`).
3. Update the rules in `SKILL.md` and the matching code in `fill_plan.py` (mics, fixed items,
   video words) to match how your team runs services.
4. Do a dry run (no `--apply`) and read every proposed change before letting it write.

Easiest path: open Claude Code in your copy and say "adapt this skill for Webster's plans."
Claude can look at your plans through the API and propose the changes.

## Changing the rules

Edit `SKILL.md` (the rules list) and `scripts/fill_plan.py` (the code). Then commit and push.
Everyone's routine picks up the change on its next run.
