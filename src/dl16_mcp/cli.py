"""Small CLI for local setup and offline smoke checks."""
import argparse
import json
from . import service


def main() -> int:
    p = argparse.ArgumentParser(prog="dl16ctl")
    cmd = p.add_subparsers(dest="command", required=True)
    cmd.add_parser("status")
    c = cmd.add_parser("capture")
    c.add_argument("--channels", default="0,1")
    c.add_argument("--sample-rate-hz", type=int, default=20_000_000)
    c.add_argument("--duration-ms", type=int, default=20)
    c.add_argument("--threshold", type=float, default=1.6)
    c.add_argument("--trigger", default="immediate")
    s = cmd.add_parser("skew")
    s.add_argument("capture_id")
    s.add_argument("--ref", type=int, required=True)
    s.add_argument("--target", type=int, required=True)
    s.add_argument("--limit-ns", type=float, default=1000)
    e = cmd.add_parser("export")
    e.add_argument("capture_id")
    e.add_argument("--channel", type=int, default=0)
    e.add_argument("--format", dest="fmt", default="vcd", choices=["vcd", "edges"])
    e.add_argument("--polarity", default="rising", choices=["rising", "falling"])
    f = cmd.add_parser("filter")
    f.add_argument("capture_id")
    f.add_argument("--channel", type=int, default=0)
    f.add_argument("--min-pulse-samples", type=int, required=True)
    f.add_argument("--out")
    se = cmd.add_parser("search")
    se.add_argument("capture_id")
    se.add_argument("--condition", action="append", required=True,
                    help="chN=rising|falling|high|low (repeatable, AND)")
    se.add_argument("--limit", type=int, default=100)
    args = p.parse_args()
    if args.command == "status":
        result = service.logic_status()
    elif args.command == "capture":
        result = service.logic_capture([int(x.strip()) for x in args.channels.split(",")],
                                       args.sample_rate_hz, args.duration_ms, args.threshold,
                                       args.trigger)
    elif args.command == "export":
        result = service.logic_export(args.capture_id, args.channel, args.fmt, args.polarity)
    elif args.command == "filter":
        result = service.logic_filter(args.capture_id, args.channel, args.min_pulse_samples,
                                      out_name=args.out)
    elif args.command == "search":
        result = service.logic_search(args.capture_id, args.condition, args.limit)
    else:
        result = service.logic_measure_skew(args.capture_id, args.ref, args.target,
                                            max_abs_error_ns=args.limit_ns)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if result.get("success") is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
