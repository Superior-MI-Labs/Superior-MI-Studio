# v2.117: multiple independently named local values, without a second compiler

## Decision

The repository has two possible ways to support normal Python local names across source/graph boundaries:

1. Persist a source-to-graph rename table. **Rejected:** duplicates `SourceDocumentSession` ownership, requires stale-revision invalidation and migration, and can silently assign an old identity to a new value.
2. Infer transient correspondences from the two fresh ASTs, **only when unique pure-expression witnesses exist**. **Adopted:** this extends the v2.116 independent-source proof, not a new document owner or importer.

For multiple renamed assignments, first pair independent pure values with uniquely matching expression ASTs. Reuse those proven mappings in later dependent expressions and iterate until every renamed assignment is matched, or stop without guessing. Expressions containing calls, `//`, `%`, effects, comprehensions, unknown producer names or duplicate matching shapes are not sufficient evidence. The existing positional path remains for ordinary identity-preserving cases. An existing graph-owned node identity, not a guessed human source name, remains authoritative. The complete trial graph must still re-lower to the edited syntax and validate as a whole.

The source file is not rewritten. Only explicitly selected function regions participate. Non-selected Python is opaque; linked generated source retains its stricter exact-baseline contract. Any unsupported change rejects the *entire* transaction, including otherwise valid edits; stale source/graph revisions reject at commit. A pure order-only edit that produces no graph change is admitted only when the existing dependency- and suite-local reorder proof succeeds.

## Qualification process

The full doctor previously sometimes completed all checks but stalled before the outer wrapper's marker. `RUN-ALL.sh` now enforces a separate configurable doctor deadline (`SMI_DOCTOR_TIMEOUT`, default 240 seconds), in addition to the pre-existing Qt smoke deadline. Expiration is a failure with retained log/tar.gz, **not** a pass, a killed working editor, or a cleanup trigger. The Python installer and successful-native-gate cleanup rules are unchanged.

## Tests and limits

`tests/test_v2117_multi_alias_proof.py` uses real graph-owned functions and verifies multi-renames, pure reordered assignments, a combined operator change, branch-local existing wire import, no-op review, undo, exact source preservation, ambiguous-producer refusal and stale-session protection. `tests/test_v2117_qualification_watchdog.py` simulates pass, failure and timeout with the actual `RUN-ALL.sh` wrapper. Full headless and host-native Qt qualification remain required for promotion.
