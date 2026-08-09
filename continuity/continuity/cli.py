"""Observable command-line surface for shared events and local recovery."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .artifacts import head_commit
from .context import ContextReconstructor
from .errors import ContinuityError
from .github import GitHubWorkState
from .recovery import RecoveryLog, rotate_recovery
from .worklog import WorkEventPublisher, WorkEventReader

SHARED_WRITE_COMMANDS = {
    "append",
    "checkpoint",
    "remap-checkpoint",
    "reopen",
    "resolve",
    "verify",
    "reconcile",
}


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


def _shared_runtime(
    args: argparse.Namespace,
    repo: Path,
) -> tuple[GitHubWorkState, WorkEventReader]:
    shared = GitHubWorkState(repo, repository=args.repository)
    return shared, WorkEventReader(repo, shared)


def _shared_write_command(
    commands: argparse._SubParsersAction,
    name: str,
    *,
    cycle_option: str = "--cycle",
) -> argparse.ArgumentParser:
    command = commands.add_parser(name)
    command.add_argument("--work", required=True)
    command.add_argument(cycle_option, required=True)
    command.add_argument("--producer", required=True)
    command.add_argument("--event-id")
    return command


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

    command = recovery_commands.add_parser("resolve-handoff")
    command.add_argument("--handoff-id", required=True)
    command.add_argument("--observation", required=True, type=_json_object)

    command = recovery_commands.add_parser("rotate")
    command.add_argument("--checkpoint-event", required=True)
    command.add_argument("--ack-durable-events-promoted", action="store_true")
    command.add_argument("--next-intent", required=True)
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

    command = _shared_write_command(shared_commands, "append")
    command.add_argument("--kind", required=True)
    command.add_argument("--summary", required=True)
    command.add_argument("--unresolved", action="store_true")
    command.add_argument("--reference", action="append")
    command.add_argument("--artifact", type=_json_object)
    command.add_argument("--details", type=_json_object)

    command = _shared_write_command(shared_commands, "checkpoint")
    command.add_argument("--commit", required=True)
    command.add_argument("--summary")
    command.add_argument("--reference", action="append")

    command = _shared_write_command(shared_commands, "remap-checkpoint")
    command.add_argument("--checkpoint-event", required=True)
    command.add_argument("--new-commit", required=True)
    command.add_argument("--reason", required=True)

    command = _shared_write_command(
        shared_commands, "reopen", cycle_option="--new-cycle"
    )
    command.add_argument("--summary", required=True)

    command = _shared_write_command(shared_commands, "resolve")
    command.add_argument("--target-event", required=True)
    command.add_argument("--summary", required=True)

    command = _shared_write_command(shared_commands, "verify")
    command.add_argument("--subject-commit", required=True)
    command.add_argument("--observation", required=True, type=_json_object)
    command.add_argument("--summary")

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
    reader: WorkEventReader | None = None,
):
    command = args.recovery_command
    if command == "rotate":
        if reader is None:
            raise AssertionError("rotation requires shared events")
        return rotate_recovery(
            recovery,
            reader,
            args.checkpoint_event,
            durable_events_acknowledged=args.ack_durable_events_promoted,
            next_intent=args.next_intent,
            local_changes_handling=args.local_changes_handling,
        )
    operations = {
        "bind": lambda: recovery.bind(
            args.work, args.cycle, args.base_checkpoint_event
        ),
        "pause": recovery.pause,
        "release": recovery.release,
        "status": recovery.status,
        "intent": lambda: recovery.intent(args.action, args.action_id, args.scope),
        "begin": lambda: recovery.begin(
            args.action_id, args.target, args.expected, args.recovery_check
        ),
        "end": lambda: recovery.end(args.action_id, args.observation),
        "handoff-open": lambda: recovery.handoff_open_operation(
            args.action_id, args.summary, args.recovery_instructions
        ),
        "resolve-handoff": lambda: recovery.resolve_handoff(
            args.handoff_id, args.observation
        ),
    }
    try:
        return operations[command]()
    except KeyError:
        raise AssertionError(command) from None


def _run_shared_read(args: argparse.Namespace, reader: WorkEventReader):
    command = args.shared_command
    operations = {
        "list": lambda: reader.events(
            args.work, cycle_id=args.cycle, kind=args.kind, pr=args.pr
        ),
        "find": lambda: reader.find_event(args.work, args.event_id),
        "unresolved": lambda: reader.unresolved_events(args.work),
        "latest-checkpoint": lambda: reader.latest_checkpoint(
            args.work,
            at_commit=args.at_commit or head_commit(reader.repo),
            cycle_id=args.cycle,
        ),
    }
    try:
        return operations[command]()
    except KeyError:
        raise AssertionError(command) from None


def _run_shared_write(args: argparse.Namespace, publisher: WorkEventPublisher):
    command = args.shared_command
    operations = {
        "append": lambda: publisher.append_significant(
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
        ),
        "checkpoint": lambda: publisher.create_checkpoint(
            args.work,
            args.cycle,
            args.commit,
            args.producer,
            summary=args.summary,
            references=args.reference,
            event_id=args.event_id,
        ),
        "remap-checkpoint": lambda: publisher.remap_checkpoint(
            args.work,
            args.cycle,
            args.checkpoint_event,
            args.new_commit,
            args.reason,
            args.producer,
            event_id=args.event_id,
        ),
        "reopen": lambda: publisher.reopen_work(
            args.work,
            args.new_cycle,
            args.producer,
            args.summary,
            event_id=args.event_id,
        ),
        "resolve": lambda: publisher.resolve_event(
            args.work,
            args.cycle,
            args.target_event,
            args.producer,
            args.summary,
            event_id=args.event_id,
        ),
        "verify": lambda: publisher.record_verification(
            args.work,
            args.cycle,
            args.subject_commit,
            args.observation,
            args.producer,
            summary=args.summary,
            event_id=args.event_id,
        ),
        "reconcile": lambda: publisher.reconcile_pending_shared_events(
            retry_missing=args.retry_missing
        ),
    }
    try:
        return operations[command]()
    except KeyError:
        raise AssertionError(command) from None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        repo = Path(args.repo).resolve()
        if args.command == "recovery":
            recovery = RecoveryLog(repo)
            reader = None
            if args.recovery_command == "rotate":
                _, reader = _shared_runtime(args, repo)
            value = _run_recovery(args, recovery, reader)
        elif args.command == "shared":
            _, reader = _shared_runtime(args, repo)
            if args.shared_command in SHARED_WRITE_COMMANDS:
                publisher = WorkEventPublisher(reader, RecoveryLog(repo))
                value = _run_shared_write(args, publisher)
            else:
                value = _run_shared_read(args, reader)
        elif args.command == "resume":
            recovery = None if args.shared_only else RecoveryLog(repo)
            shared, reader = _shared_runtime(args, repo)
            value = ContextReconstructor(
                reader, project_facts=shared, recovery=recovery
            ).load(args.work, args.cycle)
        else:
            raise AssertionError(args.command)
        _emit(value)
    except ContinuityError as error:
        print(
            json.dumps(
                {"error": {"code": error.code, "message": str(error)}},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
