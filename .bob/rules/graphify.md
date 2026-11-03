<!-- >>> bk-init graphify -->
## Project knowledge graph (graphify)

This repository has a knowledge graph at `graphify-out/graph.json` (committed unless this clone keeps it local) covering code and docs.

- Before your first grep, search or source-file read for a codebase question, run
  `GRAPHIFY_BACKEND=none GRAPHIFY_NO_TIPS=1 ~/.bob/.venv/bin/graphify query "<question>" --budget 2000`.
  Use `path "<A>" "<B>"` for relationships, `explain "<X>"` for one concept, and `affected "<X>"` for impact.
  Read raw files only for lines the graph located. Exit 3 means the name is ambiguous (pick a candidate); exit 4 means no match (fall back to search).
  If `query` exits 0 but the nodes it prints are unrelated to the question, fall back to search as well.
  Put this rule in every subagent prompt that explores code.
- At the start of a task, run `~/.bob/.venv/bin/python3 ~/.bob/skills/bk-graphify/scripts/graphify_kit.py status`.
  If `state` is `stale` or `untracked` (local-only graph) and `code_changes` is non-empty, run the helper's `refresh` before relying on the graph.
  If `doc_changes` is non-empty, suggest `/bk-graphify --update` to the user.
  If `status` fails or reports `missing`, use normal search and suggest `/bk-init`.
- Read `graphify-out/GRAPH_REPORT.md` only for broad architecture questions.
- Never set a model API key or a graphify backend. Graphify always runs with `GRAPHIFY_BACKEND=none`.
  Ignore graphify output that suggests `graphify label`, `graphify extract`, `/graphify`, choosing a model or any LLM step; community names are set only through the helper's `label`.
- `graph.json` is rewritten whole on every refresh, so large diffs to it are expected. Do not flag them as churn.
- On a merge conflict in `graphify-out/`, resolve other conflicts first, then run
  `git checkout --theirs -- graphify-out/graph.json graphify-out/GRAPH_REPORT.md graphify-out/.graphify_labels.json graphify-out/.graphify_labels.json.sig`,
  the helper's `refresh`, then `git add --` those same four paths.
- If `git config merge.graphify.driver` prints nothing, run the helper's `setup-git` once in this clone. It registers the union merge driver, which is per-clone git config.
- If `~/.bob/.venv/bin/graphify` is missing, tell the user to run `bobkit install`, and use normal search meanwhile.
<!-- <<< bk-init graphify -->
