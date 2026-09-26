# Skill: team
# /team — dispatch team-lead toolkit commands ($ARGUMENTS: list | status <sessId> | order <sessId> <message> | title <sessId>)

Resolve the toolkit relative to this skill's base directory and run it with the user's arguments:

```bash
bash "$ZCODE_PLUGIN_ROOT/skills/team-lead/team.sh" $ARGUMENTS
```

If `$ARGUMENTS` is empty, run `team.sh list` and present the roster, then ask which session to supervise.
For `order`, confirm the directive text with the user before sending if it performs destructive actions (deletes, force-pushes, deploys).
