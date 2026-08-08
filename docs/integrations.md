# Integration strategy

## Common adapter contract

Every adapter maps its platform into the same concepts:

- Project identity
- Repository and working directory
- Branch and commit
- Session or conversation ID
- Agent identity
- Lifecycle event
- Transcript or event reference
- Changed files
- Stop or compaction reason

The adapter should be thin. It should not contain memory ranking, compression policy, or database logic.

## Codex

Codex is the strongest automatic-capture target for the first implementation.

Relevant surfaces from official documentation:

- MCP servers over stdio or Streamable HTTP
- `PreCompact` before context compaction
- `PostCompact` after compaction
- `SessionStart`
- `SessionEnd`
- `PostToolUse`
- Plugin-bundled hooks

Planned behavior:

- `PreCompact`: send a bounded pre-compression observation.
- `SessionEnd`: finalize a best-effort handoff.
- `SessionStart`: make the latest relevant handoff available.
- MCP: allow explicit resume, inspect, correct, and complete operations.

Codex hook output and timeout limitations must be respected. Hook failures must not break Codex.

## Antigravity

Antigravity supports MCP and lifecycle hooks including `PostInvocation`, `PostToolUse`, and `Stop`.

Planned behavior:

- `PostInvocation`: collect lightweight progress metadata with debounce.
- `Stop`: finalize the latest available handoff and record the termination reason.
- MCP: allow explicit save and resume.

Antigravity’s stop payload exposes transcript and artifact paths in its documented schema. Handoff should prefer references and metadata over copying large artifacts.

The adapter must distinguish a normal model stop from an error, quota stop, or incomplete background task state.

## OpenCode

OpenCode supports MCP and a plugin system with session events including `session.idle`, `session.status`, `session.updated`, `session.error`, and `session.compacted`. It also exposes a compaction hook that can inject continuation-specific context.

Planned behavior:

- MCP server for resume and update operations.
- Plugin for automatic capture after idle, error, and compaction events.
- Compaction hook to preserve Handoff state in the continuation prompt.

The plugin should be optional. Users must still be able to use Handoff through MCP alone.

## Lovable

Lovable is a web builder rather than a local coding CLI. Its public integrations expose two useful paths:

1. GitHub Git sync: code is exported and synchronized through a repository.
2. Lovable MCP and custom MCP connectors: external systems can be connected while building, and external clients can manage Lovable projects.

Planned behavior:

- GitHub push webhook records commits, branches, changed files, and diffs.
- Bedrock summarizes the diff into a partial progress handoff.
- A custom Handoff MCP connector allows an explicit “save checkpoint” request from Lovable.
- OpenCode resumes from the same Git repository plus Handoff context.

Important limit: Handoff cannot claim to capture every Lovable conversation unless Lovable exposes that event. Git data captures what changed; an explicit MCP checkpoint captures reasoning and intended next steps.

## Receiving-agent behavior

The receiving agent should not be forced to use one vendor-specific prompt. It receives a standard resume packet through MCP and is instructed to:

1. Inspect the listed repository and branch.
2. Verify the current state against the files.
3. Continue from the next action.
4. Update Handoff after meaningful progress.

## Install experience

Local mode should eventually provide one setup command that:

- Creates local storage
- Detects available clients
- Installs or prints adapter configuration
- Installs hooks only after explicit consent
- Runs a health check
- Creates an example handoff

Cloud mode should use an account/project token and clearly separate user data from shared demo data.

## Adapter maturity

| Adapter | Capture | Resume | MVP status |
|---|---:|---:|---|
| Codex | lifecycle hooks | MCP | first automatic adapter |
| Antigravity | lifecycle hooks | MCP | first demo source |
| OpenCode | plugin/events | MCP | first demo receiver option |
| Lovable | GitHub + explicit MCP | MCP/dashboard | supported secondary path |
