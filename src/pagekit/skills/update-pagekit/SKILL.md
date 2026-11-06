---
name: update-pagekit
description: Update pagekit to the latest version and explain what changed, including new core components and features. Use when the user says "update pagekit", "pull in the latest pagekit", or asks whether pagekit has updates.
---

# Update pagekit

1. If the person only asked whether there are updates, run `pagekit update --check`, summarize what it lists and the
   versions it names, and stop. Otherwise continue. If they ask which version they have, run `pagekit --version`: a
   `+` after the release means the clone is that many commits past it, as a machine that follows main usually is.

2. Run:

   ```bash
   pagekit update
   ```

   If it reports uncommitted changes or another branch in the clone, tell the person what it said and ask what to do.
   Do not discard or commit anything yourself. If `pagekit` says it has no `update` command, this is an older version,
   so from the clone run `git pull --ff-only origin main`, then `uv tool install --editable . --force`, and then
   `pagekit update` to finish.

3. Do what it asks:

   - **New skills:** link each one it lists, the same way the existing pagekit skills are linked for this agent. In
     Claude Code that is `ln -s PATH ~/.claude/skills/NAME`. Check how the others are linked first.
   - **A server to restart by hand:** tell the person, unless you started it yourself.

4. Run `pagekit profile` from the current folder to confirm it still loads. If it reports a problem with a profile or
   an override, say what it is and offer to fix it.

5. Say which version it moved from and to, as it printed them. Then summarize what changed in a few plain lines, from
   the commit subjects it printed: what they can now do, not the commit list. Name any new components or features, and any change to how pages look.

6. Pages already built keep their old look until rebuilt, and the update prints how many. If the update changed how
   pages look, offer to run `pagekit rebuild --all`, from the folder whose profile the pages use. It lists any page it
   skipped because its profile does not apply there: offer to run it again from that folder. A rebuild with unchanged
   content keeps answers and comments.
