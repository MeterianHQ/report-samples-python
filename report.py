#!/usr/bin/env python3

import argparse
import csv
import http.client
import json
import logging
import os
import sys
import time
from collections import namedtuple
from datetime import datetime, timedelta, timezone

import requests

API_TOKEN_ENVVAR = "METERIAN_API_TOKEN"
BASE_URL = "https://www.meterian.com"

TIMEOUT = namedtuple("literal", "text status_code")(
    text='{"status":"timeout"}', status_code=999
)

SEVERITY_LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
VALID_TOOLS = ["BOSS", "BOSSC", "ISAAC", "SASHA", "OTHER"]


class HelpingParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write("error: %s\n" % message)
        self.print_help()
        sys.stderr.write("\n")
        sys.exit(-1)


def _log_http_requests():
    http.client.HTTPConnection.debuglevel = 1
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


def _init_logging(args):
    levels = {
        "critical": logging.CRITICAL,
        "error": logging.ERROR,
        "warn": logging.WARNING,
        "warning": logging.WARNING,
        "info": logging.INFO,
        "debug": logging.DEBUG,
    }
    level = levels.get(args.log.lower())
    if level is None:
        raise ValueError("Invalid log level: %s" % args.log)
    logging.basicConfig(level=level, format="%(levelname)s - %(message)s")
    if level == logging.DEBUG:
        _log_http_requests()
    else:
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)


def _parse_args():
    token_default = os.environ.get(API_TOKEN_ENVVAR)
    parser = HelpingParser(
        description="Generate a CSV report of all Meterian projects and their security status."
    )
    parser.add_argument(
        "-t", "--token",
        metavar="API-TOKEN",
        default=token_default,
        help="API token (default: %s env var)" % API_TOKEN_ENVVAR,
    )
    parser.add_argument(
        "-g", "--tag",
        metavar="TAG",
        default=None,
        help="Filter projects by tag",
    )
    parser.add_argument(
        "-T", "--tool",
        metavar="TOOL",
        default=None,
        choices=VALID_TOOLS,
        help="Filter by tool: %s" % ", ".join(VALID_TOOLS),
    )
    parser.add_argument(
        "-o", "--output",
        metavar="FILE",
        default="meterian_report.csv",
        help="Output CSV file path (default: meterian_report.csv)",
    )
    parser.add_argument(
        "-d", "--days",
        metavar="DAYS",
        type=int,
        default=30,
        help="Only include projects updated within this many days (default: 30)",
    )
    parser.add_argument(
        "-l", "--log",
        metavar="LOGLEVEL",
        default="warning",
        help="Log level: critical, error, warn, info, debug (default: warning)",
    )
    return parser.parse_args()


def _make_session(token):
    session = requests.Session()
    session.headers.update({"Authorization": "Token %s" % token})
    return session


def get_reports(session, days):
    url = "%s/api/v2/reports" % BASE_URL
    params = {"sinceDaysAgo": days}
    logging.debug("Fetching reports from %s with sinceDaysAgo=%d", url, days)
    try:
        resp = session.get(url, params=params, timeout=30)
    except Exception:
        logging.error("Timeout fetching reports list")
        return []
    if resp.status_code != 200:
        logging.error("Failed to list reports: HTTP %d", resp.status_code)
        return []
    return resp.json()


def get_tag_uuids(session, tag):
    url = "%s/api/v1/accounts/me/tags/%s" % (BASE_URL, tag)
    logging.debug("Fetching projects for tag '%s' from %s", tag, url)
    try:
        resp = session.get(url, timeout=30)
    except Exception:
        logging.error("Timeout fetching tag projects")
        return set()
    if resp.status_code == 404:
        logging.warning("Tag '%s' not found", tag)
        return set()
    if resp.status_code != 200:
        logging.error("Failed to fetch tag '%s': HTTP %d", tag, resp.status_code)
        return set()
    return set(resp.json().get("projects", []))


def get_full_report(session, uuid, branch):
    url = "%s/api/v1/reports/%s/full" % (BASE_URL, uuid)
    params = {"branch": branch} if branch else {}
    logging.debug("Fetching full report for %s branch=%s", uuid, branch)
    try:
        resp = session.get(url, params=params, timeout=90)
    except Exception:
        logging.warning("Timeout fetching report for %s branch=%s", uuid, branch)
        return None
    if resp.status_code == 404:
        logging.debug("No report found for %s branch=%s", uuid, branch)
        return None
    if resp.status_code != 200:
        logging.warning("Failed to fetch report for %s: HTTP %d", uuid, resp.status_code)
        return None
    return resp.json()


def count_advisories(report):
    counts = {sev: 0 for sev in SEVERITY_LEVELS}
    security = report.get("security") or {}
    for assessment in security.get("assessments", []):
        for rep in assessment.get("reports", []):
            for advice in rep.get("advices", []):
                sev = (advice.get("severity") or "").upper()
                if sev in counts:
                    counts[sev] += 1
    return counts


def format_timestamp(ts):
    if not ts:
        return ""
    try:
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            return dt.strftime("%Y/%m/%d %H:%M")
        if isinstance(ts, dict):
            return "%04d/%02d/%02d %02d:%02d" % (
                ts["year"], ts["monthValue"], ts["dayOfMonth"],
                ts["hour"], ts["minute"],
            )
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
        return dt.strftime("%Y/%m/%d %H:%M")
    except Exception:
        return str(ts)


def main():
    args = _parse_args()
    _init_logging(args)

    if not args.token:
        sys.stderr.write(
            "No API token found. Set %s or use --token.\n" % API_TOKEN_ENVVAR
        )
        sys.exit(1)

    session = _make_session(args.token)

    # Resolve project list
    all_projects = get_reports(session, args.days)
    if not all_projects:
        sys.stderr.write("No projects found or unable to reach API.\n")
        sys.exit(1)

    if args.tag:
        tag_uuids = get_tag_uuids(session, args.tag)
        projects = [p for p in all_projects if p.get("uuid") in tag_uuids]
        logging.info("Filtered to %d project(s) for tag '%s'", len(projects), args.tag)
    else:
        projects = all_projects

    total = len(projects)
    since = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y-%m-%d")
    print("Loading reports for %d project(s)/branch(es) (last %d days, since %s)..." % (
        total, args.days, since
    ))

    rows = []
    for i, proj in enumerate(projects, 1):
        logging.debug("Project data: %s", proj)
        uuid = proj.get("uuid")
        branch = proj.get("branch", "")
        tags = (proj.get("tags") or "").strip(", ")

        name = proj.get("name") or uuid
        line = "[%d/%d] %s @ %s" % (i, total, name, branch or "default")
        sys.stdout.write("\r%-120s" % line)
        sys.stdout.flush()

        report = get_full_report(session, uuid, branch)
        time.sleep(0.5)

        url = (report.get("project") or {}).get("url", "") if report else ""
        url = url.split("?")[0]

        if report is None:
            row = {
                "url": url,
                "branch": branch,
                "status": "N/A",
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "tags": tags,
                "last_updated": "",
            }
            rows.append(row)
            continue

        tool = report.get("tool", "")
        if args.tool and tool != args.tool:
            logging.debug("Skipping %s branch=%s (tool=%s)", uuid, branch, tool)
            continue

        counts = count_advisories(report)
        row = {
            "url": url,
            "branch": branch,
            "status": report.get("outcome", ""),
            "critical": counts["CRITICAL"],
            "high": counts["HIGH"],
            "medium": counts["MEDIUM"],
            "low": counts["LOW"],
            "tags": tags,
            "last_updated": format_timestamp(report.get("timestamp", "")),
        }
        rows.append(row)

    sys.stdout.write("\r" + " " * 80 + "\r")  # clear progress line
    sys.stdout.flush()

    if not rows:
        sys.stderr.write("No data to write (all entries filtered out).\n")
        sys.exit(1)

    fieldnames = ["url", "branch", "status", "critical", "high", "medium", "low", "tags", "last_updated"]
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: r["last_updated"], reverse=True))

    print("Report written to %s (%d row(s))" % (args.output, len(rows)))


if __name__ == "__main__":
    main()
