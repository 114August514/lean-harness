"""Observable command-line surface for shared events and local recovery."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .context import ContextReconstructor
from .errors import ContinuityError
from .events import WorkEvents
from .git_facts import head_commit
from .recovery import RecoveryLog
from .shared import SIGNIFICANT_KINDS, GitHubIssueSharedStore


def _json_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise argparse.ArgumentTypeError(f"invalid JSON: {error}") from error
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("expected a JSON object")
    return parsed


def _emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _local_runtime(args: argparse.Namespace):
    repo = Path(args.repo).resolve()
    recovery = RecoveryLog(repo)
    return repo, recovery


def _shared_runtime(
    args: argparse.Namespace,
    repo: Path,
    recovery: RecoveryLog | None = None,
):
    shared = GitHubIssueSharedStore(repo, repository=args.repository)
    events = WorkEvents(repo, shared, recovery)
    return shared, events


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="continuity",
        description="Project-shared work events plus per-worktree local recovery",
    )
    parser.add_argument("--repo", default=".", help="Git worktree (default: cwd)")
    parser.add_argument(
        "--repository", help="GitHub owner/name (default: discover origin)"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    recovery = commands.add_parser("recovery", help="inspect or update local recovery")
    recovery_commands = recovery.add_subparsers(dest="recovery_command", required=True)

    command = recovery_commands.add_parser("bind")
    command.add_argument("--work", required=True)
    command.add_argument("--cycle", required=True)
    command.add_argument("--base-checkpoint-event")

    recovery_commands.add_parser("pause")
    recovery_commands.add_parser("release")
    recovery_commands.add_parser("status")

    command = recovery_commands.add_parser("intent")
    command.add_argument("--action", required=True)
    command.add_argument("--action-id")
    command.add_argument("--scope", action="append", default=[])

    command = recovery_commands.add_parser("begin")
    command.add_argument("--action-id", required=True)
    command.add_argument("--target", required=True, type=_json_object)
    command.add_argument("--expected", type=_json_object)
    command.add_argument("--recovery-check", type=_json_object)

    command = recovery_commands.add_parser("end")
    command.add_argument("--action-id", required=True)
    command.add_argument("--observation", required=True, type=_json_object)

    command = recovery_commands.add_parser("handoff-open")
    command.add_argument("--action-id", required=True)
    command.add_argument("--summary", required=True)
    command.add_argument("--recovery-instructions", required=True)

    command = recovery_commands.add_parser("rotate")
    command.add_argument("--checkpoint-event", required=True)
    command.add_argument("--durable-events-confirmed", action="store_true")
    command.add_argument("--next-phase", required=True)
    command.add_argument("--local-changes-handling")

    shared = commands.add_parser("shared", help="read or publish shared Issue events")
    shared_commands = shared.add_subparsers(dest="shared_command", required=True)

    command = shared_commands.add_parser("list")
    command.add_argument("--work", required=True)
    command.add_argument("--cycle")
    command.add_argument("--kind")
    command.add_argument("--pr", type=int)

    command = shared_commands.add_parser("find")
    command.add_argument("--work", required=True)
    command.add_argument("--event-id", required=True)

    command = shared_commands.add_parser("unresolved")
    command.add_argument("--work", required=True)

    command = shared_commands.add_parser("latest-checkpoint")
    command.add_argument("--work", required=True)
    command.add_argument("--cycle")
    command.add_argument("--at-commit")

    command = shared_commands.add_parser("append")
    command.add_argument("--work", required=True)
    command.add_argument("--cycle", required=True)
    command.add_argument("--kind", required=True, choices=sorted(SIGNIFICANT_KINDS))
    command.add_argument("--producer", required=True)
    command.add_argument("--summary", required=True)
    command.add_argument("--unresolved", action="store_true")
    command.add_argument("--reference", action="append")
    command.add_argument("--artifact", type=_json_object)
    command.add_argument("--details", type=_json_object)
    command.add_argument("--event-id")

    command = shared_commands.add_parser("checkpoint")
    command.add_argument("--work", required=True)
    command.add_argument("--cycle", required=True)
    command.add_argument("--commit", required=True)
    command.add_argument("--producer", required=True)
    command.add_argument("--summary")
    command.add_argument("--reference", action="append")
    command.add_argument("--event-id")

    command = shared_commands.add_parser("remap-checkpoint")
    command.add_argument("--work", required=True)
    command.add_argument("--cycle", required=True)
    command.add_argument("--checkpoint-event", required=True)
    command.add_argument("--new-commit", required=True)
    command.add_argument("--reason", required=True)
    command.add_argument("--producer", required=True)
    command.add_argument("--event-id")

    command = shared_commands.add_parser("reopen")
    command.add_argument("--work", required=True)
    command.add_argument("--new-cycle", required=True)
    command.add_argument("--producer", required=True)
    command.add_argument("--summary", required=True)
    command.add_argument("--event-id")

    command = shared_commands.add_parser("resolve")
    command.add_argument("--work", required=True)
    command.add_argument("--cycle", required=True)
    command.add_argument("--target-event", required=True)
    command.add_argument("--producer", required=True)
    command.add_argument("--summary", required=True)
    command.add_argument("--event-id")

    command = shared_commands.add_parser("verify")
    command.add_argument("--work", required=True)
    command.add_argument("--cycle", required=True)
    command.add_argument("--subject-commit", required=True)
    command.add_argument("--observation", required=True, type=_json_object)
    command.add_argument("--producer", required=True)
    command.add_argument("--summary")
    command.add_argument("--event-id")

    command = shared_commands.add_parser("reconcile")
    command.add_argument("--retry-missing", action="store_true")

    command = commands.add_parser("resume", help="assemble replacement context")
    command.add_argument("--work")
    command.add_argument("--cycle")
    command.add_argument("--shared-only", action="store_true")
    return parser


def _run_recovery(
    args: argparse.Namespace,
    recovery: RecoveryLog,
    events: WorkEvents | None = None,
):
    command = args.recovery_command
    if command == "bind":
        return recovery.bind(args.work, args.cycle, args.base_checkpoint_event)
    if command == "pause":
        return recovery.pause()
    if command == "release":
        return recovery.release()
    if command == "status":
        return recovery.status()
    if command == "intent":
        return recovery.intent(args.action, args.action_id, args.scope)
    if command == "begin":
        return recovery.begin(
            args.action_id, args.target, args.expected, args.recovery_check
        )
    if command == "end":
        return recovery.end(args.action_id, args.observation)
    if command == "handoff-open":
        return recovery.handoff_open_operation(
            args.action_id, args.summary, args.recovery_instructions
        )
    if command == "rotate":
        if events is None:
            raise AssertionError("rotation requires shared events")
        return recovery.rotate(
            args.checkpoint_event,
            events,
            durable_events_confirmed=args.durable_events_confirmed,
            next_phase=args.next_phase,
            local_changes_handling=args.local_changes_handling,
        )
    raise AssertionError(command)


def _run_shared(args: argparse.Namespace, events: WorkEvents):
    command = args.shared_command
    if command == "list":
        return events.events(args.work, cycle_id=args.cycle, kind=args.kind, pr=args.pr)
    if command == "find":
        return events.find_event(args.work, args.event_id)
    if command == "unresolved":
        return events.unresolved_events(args.work)
    if command == "latest-checkpoint":
        return events.latest_checkpoint(
            args.work,
            at_commit=args.at_commit or head_commit(events.repo),
            cycle_id=args.cycle,
        )
    if command == "append":
        return events.append_significant(
            args.work,
            args.cycle,
            args.kind,
            args.producer,
            summary=args.summary,
            references=args.reference,
            unresolved=args.unresolved,
            artifact=args.artifact,
            details=args.details,
            event_id=args.event_id,
        )
    if command == "checkpoint":
        return events.create_checkpoint(
            args.work,
            args.cycle,
            args.commit,
            args.producer,
            summary=args.summary,
            references=args.reference,
            event_id=args.event_id,
        )
    if command == "remap-checkpoint":
        return events.remap_checkpoint(
            args.work,
            args.cycle,
            args.checkpoint_event,
            args.new_commit,
            args.reason,
            args.producer,
            event_id=args.event_id,
        )
    if command == "reopen":
        return events.reopen_work(
            args.work,
            args.new_cycle,
            args.producer,
            args.summary,
            event_id=args.event_id,
        )
    if command == "resolve":
        return events.resolve_event(
            args.work,
            args.cycle,
            args.target_event,
            args.producer,
            args.summary,
            event_id=args.event_id,
        )
    if command == "verify":
        return events.record_verification(
            args.work,
            args.cycle,
            args.subject_commit,
            args.observation,
            args.producer,
            summary=args.summary,
            event_id=args.event_id,
        )
    if command == "reconcile":
        return events.reconcile_pending_shared_events(retry_missing=args.retry_missing)
    raise AssertionError(command)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        repo = Path(args.repo).resolve()
        if args.command == "recovery":
            _, recovery = _local_runtime(args)
            events = None
            if args.recovery_command == "rotate":
                _, events = _shared_runtime(args, repo, recovery)
            value = _run_recovery(args, recovery, events)
        elif args.command == "shared":
            write_commands = {
                "append",
                "checkpoint",
                "remap-checkpoint",
                "reopen",
                "resolve",
                "verify",
                "reconcile",
            }
            recovery = (
                RecoveryLog(repo) if args.shared_command in write_commands else None
            )
            _, events = _shared_runtime(args, repo, recovery)
            value = _run_shared(args, events)
        elif args.command == "resume":
            _, recovery = _local_runtime(args)
            shared, events = _shared_runtime(args, repo, recovery)
            value = ContextReconstructor(
                repo, events, recovery, project_facts=shared
            ).load(args.work, args.cycle, shared_only=args.shared_only)
        else:
            raise AssertionError(args.command)
        _emit(value)
    except ContinuityError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
