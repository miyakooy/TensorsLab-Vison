# TensorsLab Vision Reliable Production Workflow Roadmap

[简体中文](prd-reliability-roadmap.zh-CN.md) · [日本語](prd-reliability-roadmap.ja.md) · [한국어](prd-reliability-roadmap.ko.md)

## Product position

TensorsLab Vision provides image and video generation for agents together with an auditable, resumable visual-production workflow. The roadmap adopts useful ideas from agentao—approval binding, explicit states, atomic persistence, and resource access—without importing a general-purpose agent runtime.

## Priorities

| Priority | Phase | Problem | Delivery |
| --- | --- | --- | --- |
| P0 | Approval and quality gates | Approved content can diverge from execution; generated output can be mistaken for deliverable output | Content digests, asset hashes, task-level reapproval, separate QA and delivery states |
| P0 | Task persistence and recovery | A stopped process or polling timeout can lead to duplicate submission and charges | `submit/status/wait/download`, persisted task IDs, atomic state records |
| P1 | Structured results | Agents must infer success from log text | Unified JSON results for generation, query, download, and QA failures |
| P1 | Bounded batch execution | SKU, ratio, and shot plans require manual execution | Concurrency limits, completed-task skipping, resumable batch progress |
| P2 | Lightweight MCP access | Different agent hosts cannot discover and call the capabilities consistently | MCP Tools and Resources that reuse the existing clients |

## PR 1: Approval digests and QA states

Status: implemented and ready for review.

Approval calculates a SHA-256 digest for each task. It covers project context, immutable facts, prompts, shot definitions, generation settings, approved dispatch overrides, and the content hashes of local input assets. Dispatch recalculates the digest and stops when approved content changes.

Revising one shot revokes only that task's digest. Generation, QA, and delivery are recorded separately. Product truth, visual quality, text and rights, and publication review must each pass or be marked `not_applicable` before `delivery_status` becomes `ready`.

## PR 2: Task recovery and structured results

Planned work:

1. Add separate `submit`, `status`, `wait`, and `download` operations while preserving the current convenience command.
2. Atomically persist the task ID and request summary immediately after submission.
3. Return unified JSON for generation state, download state, files, and actionable error codes.
4. Resume polling when a task ID exists; retry only the download when downloading fails.
5. Record `submission_unknown` when submission outcome is uncertain. Do not automatically resubmit a paid job until the server supports idempotency keys.

Acceptance: a stopped process can resume the same task; a polling timeout is not reported as generation failure; a download retry never creates a new generation task.

## PR 3: Bounded batch executor

The executor will consume structured dispatch objects rather than arbitrary shell text, enforce concurrency and batch-size limits, record task IDs and progress, skip submitted or completed work, and preserve server-accepted tasks when new dispatch is stopped.

Acceptance: restart does not duplicate submissions, one failed item does not lose batch progress, and concurrency never exceeds the configured limit.

## PR 4: MCP Tools and Resources

Initial Tools will preview requests, submit generation, query tasks, and download results. Resources will expose model capabilities, parameter documentation, task records, and result links. MCP must reuse the existing validation and task store instead of creating a second generation implementation.

Remote MCP Skills, OAuth, a general Durable framework, full-screen TUI, Codemode, and general multi-agent orchestration are outside this roadmap. Paid generation submissions must not inherit automatic reconnect-and-retry behavior.

## Success measures

- Changing an approved prompt, parameter, constraint, or asset blocks dispatch.
- Revising one shot revokes only that task's approval.
- Incomplete or failed QA cannot enter delivery or assembly.
- A stopped process can resume the same server task by task ID.
- Download retry does not submit another generation request.
- Batch execution does not resubmit registered tasks.
