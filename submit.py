"""Submit your case-study solution to the grader.

Usage:
    python submit.py URL                 # zip + upload using your case-study link
    python submit.py URL --zip-only      # just write submission.zip, don't upload
    python submit.py URL --zip file.zip  # skip zipping, upload an existing file

`URL` is the case-study link you were issued, e.g.

    https://portal.instalily.ai/case-study/abcde

The script reads your submission id (the final path segment, `abcde`) straight
from that link and uploads your archive to the grader. You don't pass an
endpoint or id separately. Late submissions are still accepted, but are marked
as late for the hiring team.

(`--endpoint` overrides the upload target for local testing against a grader you
booted yourself; you won't need it for a real submission.)
"""

from __future__ import annotations

import argparse
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

# The deployed grader submit function. The case-study link only supplies your
# submission id; the upload always goes here.
DEFAULT_ENDPOINT = "https://us-central1-hiring-479819.cloudfunctions.net"
DEFAULT_ZIP_NAME = "submission.zip"

EXCLUDE_DIRS = {
    "node_modules",
    ".venv",
    ".grader_venv",
    "__pycache__",
    ".turbo",
    ".idea",
    ".pnpm-store",
    ".git",
}
EXCLUDE_NAMES = {".DS_Store", DEFAULT_ZIP_NAME}


def _slug_from_url(url: str) -> str:
    """Extract the submission id (slug) from a case-study link.

    The slug is the final non-empty path segment. For example,
    ``https://portal.instalily.ai/case-study/abcde`` → ``"abcde"``.
    """
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(
            f"not a valid case-study link: {url!r}\n"
            "expected something like https://portal.instalily.ai/case-study/abcde"
        )
    segments = [seg for seg in parsed.path.split("/") if seg]
    if not segments:
        raise ValueError(
            f"no submission id found in link: {url!r}\n"
            "expected a slug at the end, e.g. .../case-study/abcde"
        )
    return segments[-1]


def _build_zip(root: Path, out_path: Path) -> None:
    file_count = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            if any(part in EXCLUDE_DIRS for part in path.parts):
                continue
            if path.name in EXCLUDE_NAMES:
                continue
            if path.is_file():
                zf.write(path, path.relative_to(root))
                file_count += 1
    size = out_path.stat().st_size
    print(f"  wrote {file_count} files, {size:,} bytes → {out_path}", file=sys.stderr)


def _post(endpoint: str, submission_id: str, zip_path: Path) -> int:
    blob = zip_path.read_bytes()
    boundary = f"----submit-{secrets.token_hex(8)}"
    id_part = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="id"\r\n\r\n'
        f"{submission_id}\r\n"
    ).encode()
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="submission"; filename="{zip_path.name}"\r\n'
        f"Content-Type: application/zip\r\n\r\n"
    ).encode()
    tail = f"\r\n--{boundary}--\r\n".encode()

    request = urllib.request.Request(
        f"{endpoint.rstrip('/')}/submit",
        data=id_part + head + blob + tail,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(request) as resp:
            print(resp.read().decode())
            return 0
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode()}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"connection failed: {exc.reason}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    _ = parser.add_argument(
        "url",
        help="Your case-study link, e.g. https://portal.instalily.ai/case-study/abcde",
    )
    _ = parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help="Override the upload target (for local testing). Defaults to the grader.",
    )
    _ = parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parent),
        help="Directory to zip (defaults to this script's directory).",
    )
    _ = parser.add_argument(
        "--zip",
        dest="zip_path",
        help="Use this existing zip instead of building one.",
    )
    _ = parser.add_argument(
        "--zip-only",
        action="store_true",
        help="Build the zip and exit without uploading.",
    )
    args = parser.parse_args()

    try:
        submission_id = _slug_from_url(args.url)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    endpoint = args.endpoint

    if args.zip_path:
        zip_path = Path(args.zip_path).resolve()
        if not zip_path.is_file():
            print(f"zip not found: {zip_path}", file=sys.stderr)
            return 2
        print(f"using existing zip: {zip_path}", file=sys.stderr)
    else:
        root = Path(args.root).resolve()
        zip_path = root / DEFAULT_ZIP_NAME
        print(f"zipping {root}...", file=sys.stderr)
        _build_zip(root, zip_path)

    if args.zip_only:
        print(str(zip_path))
        return 0

    print(f"uploading to {endpoint} as '{submission_id}'...", file=sys.stderr)
    return _post(endpoint, submission_id, zip_path)


if __name__ == "__main__":
    raise SystemExit(main())
