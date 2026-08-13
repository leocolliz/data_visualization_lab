"""Download the raw MIMIT extracts this project is built on.

`data/` is gitignored, so a fresh clone has the code and none of the inputs.
This puts them back in the layout `config.py` expects:

    python scripts/fetch_data.py          # ~1.3 GB down, ~430 MB kept
    python scripts/build_panel.py         # then the pipeline as usual

What it fetches, and why exactly this much:

*Prices.* MIMIT publishes one CSV per day, distributed as quarterly tarballs.
This project samples one weekday per week (`config.SAMPLE_WEEKDAY`), so of the
~91 daily files in a quarter only the 13 Mondays are kept. The other 78 are read
out of the archive and dropped: the ministry offers no per-day download for past
dates, so the whole quarter has to come down either way.

*Registry.* Published the same way. `geo.load_registry` takes the union of one
snapshot per quarter, so this keeps the first sampled Monday of each quarter --
which is what makes the 8 files on disk the 8 files it reads.

*Boundaries.* Province polygons from openpolis/geojson-italy.

The scope comes from `config.py` rather than from constants here, so moving
START, END or SAMPLE_WEEKDAY changes what this downloads without editing it.

Re-running is cheap. Anything already on disk is left alone, a half-finished
download resumes instead of restarting, and `--force` re-fetches regardless.
"""

import argparse
import shutil
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath

import config

MIMIT = "https://opendatacarburanti.mise.gov.it/categorized"
GEOJSON = ("https://raw.githubusercontent.com/openpolis/geojson-italy"
           "/master/geojson/limits_IT_provinces.geojson")

# The ministry names both archives `{year}_{quarter}_tr.tar.gz` and tells them
# apart only by directory, so the local copies get the kind back in the name.
PRICES = ("prezzo_alle_8", "prezzo")
REGISTRY = ("anagrafica_impianti_attivi", "anagrafica")

TIMEOUT = 120
ATTEMPTS = 3
# The default urllib agent is refused by some public-sector CDNs.
AGENT = "where-you-refuel/1.0 (dataviz coursework; +https://www.mimit.gov.it)"


def quarters():
    """The (year, quarter) buckets the sampled days fall into, oldest first."""
    out = {}
    for d in config.sample_dates():
        out.setdefault((d.year, (d.month - 1) // 3 + 1), []).append(d)
    return out


def targets(qs):
    """{(year, quarter): (prices wanted, registry wanted)} as bare filenames."""
    return {
        q: ({config.price_file(d).name for d in days},
            # One snapshot per quarter is enough for the union, and taking the
            # first *sampled* day rather than the first calendar day keeps the
            # registry on the same weekly grid as the prices.
            {f"anagrafica_impianti_attivi-{days[0]:%Y%m%d}.csv"})
        for q, days in qs.items()
    }


def human(n):
    return f"{n / 1048576:.0f} MB" if n else "unknown size"


def download(url, dest, *, force=False, progress=True):
    """Stream `url` to `dest`, resuming a partial download if one is present.

    The download lands in a `.part` file and is renamed only once complete, so
    an interrupted run can never leave a truncated archive that looks finished.
    """
    if dest.exists() and not force:
        return False

    part = dest.with_name(dest.name + ".part")
    if force and part.exists():
        part.unlink()
    have = part.stat().st_size if part.exists() else 0

    for attempt in range(1, ATTEMPTS + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": AGENT})
            if have:
                req.add_header("Range", f"bytes={have}-")
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                # A server that ignores Range replies 200 with the whole file;
                # appending that to what we already hold would corrupt it.
                resuming = have and r.status == 206
                if not resuming:
                    have = 0
                total = int(r.headers.get("Content-Length") or 0) + have
                done, tick = have, time.monotonic()
                with open(part, "ab" if resuming else "wb") as fh:
                    while chunk := r.read(1 << 20):
                        fh.write(chunk)
                        done += len(chunk)
                        if progress and time.monotonic() - tick > 0.5:
                            tick = time.monotonic()
                            pct = f" {100 * done / total:5.1f}%" if total else ""
                            print(f"\r    {human(done)}{pct}", end="", flush=True)
            if progress:
                print(f"\r    {human(done)}         ")
            part.replace(dest)
            return True
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            have = part.stat().st_size if part.exists() else 0
            if attempt == ATTEMPTS:
                raise SystemExit(f"    failed after {ATTEMPTS} attempts: {exc}")
            print(f"\r    {exc} - retrying ({attempt}/{ATTEMPTS - 1})")
            time.sleep(2 * attempt)


def extract(archive, keep, dest_dir):
    """Pull just the members named in `keep` out of `archive` into `dest_dir`.

    Members are matched on basename and written to a path we choose, rather than
    handed to `extractall`: a tar entry is free to call itself `../../anything`,
    and this way the archive never gets to decide where a file lands.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    got = set()
    with tarfile.open(archive, "r:gz") as tf:
        for member in tf:
            name = PurePosixPath(member.name).name
            if not member.isfile() or name not in keep or name in got:
                continue
            src = tf.extractfile(member)
            if src is None:
                continue
            with open(dest_dir / name, "wb") as fh:
                shutil.copyfileobj(src, fh)
            got.add(name)
    return got


def fetch_quarter(kind, year, q, keep, dest_dir, *, store, force, progress):
    """Download one quarterly archive if anything in `keep` is still missing."""
    remote, local = kind
    missing = {n for n in keep if not (dest_dir / n).exists()} if not force else set(keep)
    if not missing:
        print(f"  {local} {year} Q{q}: {len(keep)} file(s) already present")
        return set()

    url = f"{MIMIT}/{remote}/{year}/{year}_{q}_tr.tar.gz"
    archive = store / f"{local}_{year}_{q}.tar.gz"
    print(f"  {local} {year} Q{q}: {len(missing)} of {len(keep)} file(s) missing")
    if archive.exists() and not force:
        print(f"    reusing {archive.name}")
    else:
        download(url, archive, force=force, progress=progress)
    got = extract(archive, keep, dest_dir)
    short = keep - got
    if short:
        print(f"    WARNING not in the archive: {', '.join(sorted(short))}")
    return got


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true",
                    help="re-download and re-extract even if files are present")
    ap.add_argument("--keep-archives", action="store_true",
                    help="leave the quarterly tarballs in data/raw/ (~1.3 GB) "
                         "instead of discarding them once extracted")
    ap.add_argument("--quiet", action="store_true", help="no progress meter")
    args = ap.parse_args(argv)

    progress = not args.quiet and sys.stdout.isatty()
    config.PRICES.mkdir(parents=True, exist_ok=True)
    config.REGISTRY.mkdir(parents=True, exist_ok=True)

    qs = quarters()
    want = targets(qs)
    n_prices = sum(len(p) for p, _ in want.values())
    print(f"Scope from config.py: {config.START} to {config.END}, "
          f"weekday {config.SAMPLE_WEEKDAY} -> {n_prices} price files "
          f"and {len(qs)} registry snapshots across {len(qs)} quarters.\n")

    # Without --keep-archives the tarballs are scratch: downloaded, read once,
    # and gone before the next quarter, so the peak cost is one archive.
    with tempfile.TemporaryDirectory(prefix="fetch-", dir=config.RAW) as tmp:
        store = config.RAW if args.keep_archives else Path(tmp)
        for (year, q), (prices, registry) in want.items():
            fetch_quarter(PRICES, year, q, prices, config.PRICES,
                          store=store, force=args.force, progress=progress)
            fetch_quarter(REGISTRY, year, q, registry, config.REGISTRY,
                          store=store, force=args.force, progress=progress)
            if not args.keep_archives:
                for leftover in Path(tmp).glob("*.tar.gz"):
                    leftover.unlink()

    geo = config.RAW / "provinces.geojson"
    if geo.exists() and not args.force:
        print("  boundaries: provinces.geojson already present")
    else:
        print("  boundaries: provinces.geojson")
        download(GEOJSON, geo, force=args.force, progress=progress)

    # Report against what the pipeline will actually look for, not against what
    # this script believes it wrote.
    have_prices = sum(config.price_file(d).exists() for d in config.sample_dates())
    have_registry = len(config.registry_files())
    print(f"\nprices     {have_prices}/{n_prices}")
    print(f"registry   {have_registry}/{len(qs)}")
    print(f"boundaries {'1/1' if geo.exists() else '0/1'}")

    if have_prices == n_prices and have_registry == len(qs) and geo.exists():
        print("\nComplete. Next: python scripts/build_panel.py")
        return 0
    print("\nIncomplete - re-run to retry the missing pieces.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
