# v2.137 — Reject unknown initial Python focus before source-root publication

## Confirmed gap

When the original Python source root was still uninitialized, the common
`_open_navigation_route` accepted a focused source route by first calling
`_open_python_source_path(path, bootstrap_root=True)` as a **whole-file**
source open and then calling `navigate_source(scope)`. A missing lexical
scope could fail at the latter step *after* publishing the root document,
initial navigation history, Qt selection and provider aliases, despite the
route returning false. This violates the same refusal atomicity contract
used for already-initialized source roots and secondary source tabs.

## Alternatives

A. Independently preflight a focus route in the dispatcher using a fresh
source owner, then open the file again. **Rejected:** duplicated disk
reads and source revisions leave a time-of-check/time-of-use gap.
B. Extend the existing source-opening transaction with an optional
`focus_scope`. After acquiring a single `SourceDocumentSession` and
before registering any view, use the established
`resolve_source_session_route` on **that same owner** to validate an
actual focus route. Keep the original whole-file root open followed by
`navigate_source` so the Back entry still returns to the whole-file
view. **Selected.** This adds no parser, registry, source writer or graph
authority.

If source syntax is invalid, ordinary whole-file text open remains
permitted, but a focus request refuses without opening. Any unknown or
deleted focus refuses without changing root session, foreground, active
provider aliases, live document map, secondary source route/camera or
loaded editor. A valid first focus initializes the root and retains
whole-file Back history.

## Evidence and rollback

`tests/test_v2137_initial_root_focus.py` characterizes the preflight
ordering and initial-root dispatch. The native Qt stage
`uninitialized-source-root-focus-atomicity` extends v2.135's isolated
secondary-source fixture: refused missing focus retains the previously
captured Qt/source state, then valid focus opens the root and leaves an
explicit whole-file Back destination while the secondary session stays
intact.

Older v2.122/v2.132/v2.135 structural assertions are updated to reflect
the stronger preflight contract without removing their original checks.
Rollback is this bounded transaction extension to v2.136. GitHub CI
and separate Linux Mint host qualification remain required.
