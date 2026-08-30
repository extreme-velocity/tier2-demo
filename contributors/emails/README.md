# Contributor email → GitHub login mappings

One file per commit-author email. File **name** = the exact email from
`git log --format='%ae'`; file **content** = the GitHub login on the first
non-comment line (`#` lines are comments, use them for the PR reference).

```
echo "janedoe" > contributors/emails/jane.doe@example.com
```

Why one file per email? Every salvage PR edits this map — file additions
never conflict, a shared dict would. (Upstream replaced exactly such a
dict after constant merge conflicts.)

- GitHub noreply emails (`<id>+<login>@users.noreply.github.com`) auto-resolve — no file needed.
- The Contributor Attribution Check CI job fails a PR with an unmapped email and prints the exact command to fix it.
