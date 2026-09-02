"""Entry point: `meridiand` or `python -m meridiand`."""

from __future__ import annotations

import argparse
import logging
import sys

from .engine import DEFAULT_TICK_HZ, Engine
from .server import DEFAULT_HOST, DEFAULT_PORT, build_server, state_dir, write_token


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="meridiand", description=__doc__)
    parser.add_argument("command", nargs="?", default="serve", choices=["serve", "doctor"],
                        help="serve the local API (default), or run an end-to-end preflight")
    parser.add_argument("--host", default=DEFAULT_HOST, help="bind address (loopback by default)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--tick-hz", type=float, default=DEFAULT_TICK_HZ,
                        help="location updates per second during playback")
    parser.add_argument("--jitter", type=float, default=0.0, metavar="METRES",
                        help="wander a fixed location by up to this many metres")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.host != DEFAULT_HOST:
        logging.warning("binding to %s exposes location control beyond this machine", args.host)

    if args.command == "doctor":
        from .doctor import main as doctor_main

        return doctor_main()

    engine = Engine(tick_hz=args.tick_hz, jitter_m=args.jitter)
    engine.start()

    token = write_token()
    server = build_server(engine, token, host=args.host, port=args.port)

    logging.info("meridiand listening on http://%s:%d", args.host, args.port)
    logging.info("token: %s/token", state_dir())

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("shutting down")
    finally:
        server.shutdown()
        engine.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
