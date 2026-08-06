"""命令行入口：``python -m continuity <command>``。

这是契约第八节"实现应支持的操作"的可运行入口，
用于端到端验证。Runtime adapter 的完整接入在后续工作中完成。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .context import ResumeContext
from .recovery import RecoveryLog
from .store import JsonlStore, StoreError
from .worklog import WorkLog


def _json_arg(value: str) -> dict:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as e:
        raise argparse.ArgumentTypeError(f"invalid JSON: {e}") from e
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("expected a JSON object")
    return parsed


def _repo(path: str | None) -> Path:
    return Path(path).resolve() if path else Path.cwd()


def _store(args) -> JsonlStore:
    return JsonlStore(_repo(getattr(args, "repo", None)))


def _parts(args) -> tuple[JsonlStore, RecoveryLog, WorkLog]:
    store = _store(args)
    return store, RecoveryLog(store), WorkLog(store)


def _emit(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _fields(args) -> dict:
    fields = dict(getattr(args, "fields", None) or {})
    for key in ("commit", "subject_commit", "pr", "observation"):
        value = getattr(args, key, None)
        if value is not None:
            fields[key] = value
    return fields


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="continuity")
    parser.add_argument("--repo", help="repository path (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)

    # recovery
    rec = sub.add_parser("recovery", help="per-worktree recovery log")
    rec_sub = rec.add_subparsers(dest="recovery_command", required=True)

    p = rec_sub.add_parser("bind", help="bind worktree to a work unit")
    p.add_argument("--work", required=True)
    p.add_argument("--cycle", required=True)
    p.add_argument("--base-checkpoint", default=None)

    rec_sub.add_parser("pause", help="pause the current binding")
    rec_sub.add_parser("release", help="release the current binding")

    p = rec_sub.add_parser("intent", help="record current intent")
    p.add_argument("--action", required=True)
    p.add_argument("--action-id", default=None)
    p.add_argument("--scope", action="append", default=[])

    p = rec_sub.add_parser("begin", help="record begin before a side effect")
    p.add_argument("--action-id", required=True)
    p.add_argument("--target", type=_json_arg, required=True)
    p.add_argument("--expected", type=_json_arg, default=None)
    p.add_argument("--recovery-check", type=_json_arg, default=None)

    p = rec_sub.add_parser("end", help="record end after a reliable observation")
    p.add_argument("--action-id", required=True)
    p.add_argument("--observation", type=_json_arg, required=True)

    rec_sub.add_parser("status", help="show binding, latest intent and open begins")

    p = rec_sub.add_parser("rotate", help="rotate records absorbed by a checkpoint")
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--force", action="store_true")

    # work log
    wl = sub.add_parser("worklog", help="project work log (partitioned by work unit)")
    wl_sub = wl.add_subparsers(dest="worklog_command", required=True)

    p = wl_sub.add_parser("append", help="append a work event")
    p.add_argument("--work", required=True)
    p.add_argument("--kind", required=True)
    p.add_argument("--cycle", default=None)
    p.add_argument("--summary", default=None)
    p.add_argument("--unresolved", action="store_true")
    p.add_argument("--resolves", type=int, action="append", default=None)
    p.add_argument("--commit", default=None)
    p.add_argument("--subject-commit", default=None)
    p.add_argument("--pr", type=int, default=None)
    p.add_argument("--observation", type=_json_arg, default=None)
    p.add_argument("--fields", type=_json_arg, default=None)

    p = wl_sub.add_parser("reopen", help="reopen an issue partition with a new cycle")
    p.add_argument("--work", required=True)
    p.add_argument("--new-cycle", required=True)
    p.add_argument("--summary", default=None)

    p = wl_sub.add_parser("checkpoint", help="explicitly mark a commit as checkpoint")
    p.add_argument("--work", required=True)
    p.add_argument("--cycle", required=True)
    p.add_argument("--commit", required=True)

    p = wl_sub.add_parser(
        "remap-checkpoint", help="record commit mapping after history rewrite"
    )
    p.add_argument("--work", required=True)
    p.add_argument("--cycle", required=True)
    p.add_argument("--old", required=True)
    p.add_argument("--new", required=True)
    p.add_argument("--reason", required=True)

    p = wl_sub.add_parser("list", help="list work events")
    p.add_argument("--work", required=True)
    p.add_argument("--cycle", default=None)
    p.add_argument("--kind", default=None)
    p.add_argument("--pr", type=int, default=None)

    p = wl_sub.add_parser("latest-checkpoint", help="locate the latest checkpoint")
    p.add_argument("--work", required=True)
    p.add_argument("--at-commit", default=None)

    p = wl_sub.add_parser("since", help="events after a checkpoint")
    p.add_argument("--work", required=True)
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--at-commit", default=None)
    p.add_argument("--cycle", default=None)
    p.add_argument("--kind", default=None)
    p.add_argument("--pr", type=int, default=None)

    p = wl_sub.add_parser("unresolved", help="unresolved older events")
    p.add_argument("--work", required=True)

    # resume
    p = sub.add_parser("resume", help="load recovery inputs for a replacement agent")
    p.add_argument("--work", default=None)
    p.add_argument("--cycle", default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "recovery":
            _, recovery, _ = _parts(args)
            cmd = args.recovery_command
            if cmd == "bind":
                _emit(recovery.bind(args.work, args.cycle, args.base_checkpoint))
            elif cmd == "pause":
                _emit(recovery.pause())
            elif cmd == "release":
                _emit(recovery.release())
            elif cmd == "intent":
                _emit(recovery.intent(args.action, args.action_id, args.scope))
            elif cmd == "begin":
                _emit(
                    recovery.begin(
                        args.action_id, args.target, args.expected, args.recovery_check
                    )
                )
            elif cmd == "end":
                _emit(recovery.end(args.action_id, args.observation))
            elif cmd == "status":
                _emit(recovery.status())
            elif cmd == "rotate":
                _emit(recovery.rotate(args.checkpoint, force=args.force))
        elif args.command == "worklog":
            _, _, worklog = _parts(args)
            cmd = args.worklog_command
            if cmd == "append":
                _emit(
                    worklog.append(
                        args.work,
                        args.kind,
                        cycle_id=args.cycle,
                        summary=args.summary,
                        unresolved=args.unresolved,
                        resolves=args.resolves,
                        fields=_fields(args),
                    )
                )
            elif cmd == "reopen":
                _emit(worklog.reopen(args.work, args.new_cycle, args.summary))
            elif cmd == "checkpoint":
                _emit(worklog.checkpoint(args.work, args.cycle, args.commit))
            elif cmd == "remap-checkpoint":
                _emit(
                    worklog.remap_checkpoint(
                        args.work, args.cycle, args.old, args.new, args.reason
                    )
                )
            elif cmd == "list":
                _emit(
                    worklog.events(
                        args.work, cycle_id=args.cycle, kind=args.kind, pr=args.pr
                    )
                )
            elif cmd == "latest-checkpoint":
                _emit(worklog.latest_checkpoint(args.work, at_commit=args.at_commit))
            elif cmd == "since":
                _emit(
                    worklog.events_since(
                        args.work,
                        args.checkpoint,
                        at_commit=args.at_commit,
                        cycle_id=args.cycle,
                        kind=args.kind,
                        pr=args.pr,
                    )
                )
            elif cmd == "unresolved":
                _emit(worklog.unresolved_events(args.work))
        elif args.command == "resume":
            store, recovery, worklog = _parts(args)
            _emit(ResumeContext(store, worklog, recovery).load(args.work, args.cycle))
    except StoreError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
