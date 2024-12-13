#!/usr/bin/env python3.13
"""make.py <python version>

Dumps build config informations:
    # builds the pyrun for python 3.12.4 (the first in 3.12.*)
    make.py 3.12

    # builds the exact 3.12.4 version
    make.py 3.12 --micro 4


"""
import os
import sys
import dataclasses as dc
import subprocess
import json
from pathlib import Path
import argparse

PYVERSIONS = {
    "3.12": ["3.12.4"],
}

# Note that you have to keep this in sync with pyrun/makepyrun.py
PACKAGEVERSION = "2.6.0"


@dc.dataclass
class Config:
    version: str
    dest: Path
    package: str
    PLATFORM: str

    PYTHONFULLVERSION: (int, int, int)
    
    # Python Unicode version
    #
    # Only needed for Python 2 and early Python 3.x versions
    #
    PYTHONUNICODE: str


    PYRUNVERSION: str = ""
    PYTHONVERSION: str = ""
    PYTHONMAJORVERSION: str = ""
    PYTHONMINORVERSION: str = ""

    # Python 3 ABI flags (see PEP 3149)
    #
    # These should probably be determined by running a standard Python 3 and
    # checking sys.abiflags. Hardcoding them here for now, since they rarely
    # change.
    #
    # The ABI flags were only used in paths for Python 3.x - 3.7. Python
    # 3.8+ no longer use these flags for e.g. include file paths.
    #
    PYTHONABI: str = "m"


    # Packages and modules to exclude from the runtime (note that each
    # module has to be prefixed with "-x ") for both Python 2 and 3.  Note
    # that makepyrun.py has its own predefined list of modules to exclude
    # in the module search. This list of excludes provides extra
    # protection against modules which are still found by the search and
    # should not be included in pyrun. They can also be used to further
    # trim down the module/package list, if needed.
    #
    EXCLUDES: list[str] = dc.field(default_factory=lambda: [
        "test",
        "Tkinter",
        "tkinter",
        "setuptools",
        "pydoc_data",
        "pip",
    ])

    PACKAGENAME: str = "egenix-pyrun"
    PACKAGEVERSION: str = PACKAGEVERSION
    RELEASETAG: str = "!egenix-pyrun-{PACKAGEVERSION}"
    BINARY_DISTRIBUTION: str = "!{PACKAGENAME}-{PACKAGEVERSION}-py{PYTHONVERSION}_{PYTHONUNICODE}-{PLATFORM}"
    DISTDIR: str = "dist"
    BINARY_DISTRIBUTION_ARCHIVE: str = "!{DISTDIR}/{BINARY_DISTRIBUTION}.tgz"
    PYRUN_GENERIC: str = "pyrun"
    PYRUN: str = "{PYRUN_GENERIC}{PYRUNVERSION}"
    PYRUN_SSL: Path | None = None
    PYRUN_DEBUG: str = "!{PYRUN}-debug"
    PYRUN_STANDARD: str = "!{PYRUN}-standard"
    PYRUN_UPX: str = "!{PYRUN}-upx"
    BASEDIR: str = "!build/{PYTHONVERSION}-{PYTHONUNICODE}"
    BUILDDIR: Path = Path("!{BASEDIR}/pyrun-installation")
    BINDIR: str = "!{BUILDDIR}/bin"
    

def get_platform() -> str:
    """returns the current system tag

    Eg.
        print(get_platform())
        linux-armv7l
    """
    txt = subprocess.check_output(["uname", "-s", "-m"], encoding="utf-8")
    return txt.replace(" ", "-").lower().strip()


def get_ssl() -> Path:
    """discovers the ssl devel root

    Eg.
        print(get_ssl())
        Path("/usr")
    """
    if ssl := os.getenv("SSL"):
        return Path(ssl)
    candidates = [
        ("/usr/include/openssl/ssl.h", "/usr",),
        ("/usr/local/ssl/include/openssl/ssl.h", "/usr/local/ssl",),
        ("/usr/contrib/ssl/include/openssl/ssl.h", "/usr/contrib/ssl",),
        ("/usr/sfw/include/openssl/ssl.h", "/usr/sfw"),
    ]
    for path, ret in candidates:
        if (src := Path(path)).exists():
            return Path(ret)
    return Path("/usr")


def get_full_target_pythonversion(version: str, micro: None | int) -> None | str:
    """lookup in PYVERSIONS for a version, and possibly for a version.micro

    Eg.
        get_full_target_pythonversion("3.12", None)
        "3.12.4" # first fullversion in the 3.12.* line
    
        get_full_target_pythonversion("3.12", 4)
        "3.12.4" # specific version

        get_full_target_pythonversion("3.12", 99)
        None
    """

    all_candidates = [v for versions in PYVERSIONS.values() for v in versions]
    check = f"{version}.{micro}" if micro else version
    if check in all_candidates:
        return check
    return PYVERSIONS.get(check, [None])[0]
    

def show_version(config):
    print("""
Python version (executable): {sys.version} ({sys.executable})
PyRun version: {PACKAGEVERSION}
Python version: {PYTHONFULLVERSION} ('{PYTHONVERSION}' = '{PYTHONMAJORVERSION}'.'{PYTHONMINORVERSION}')
PyRun platform: {PLATFORM}
PyRun Unicode: {PYTHONUNICODE}
PyRun distribution name: {BINARY_DISTRIBUTION}.tgz
PyRun binary: {BINDIR}/{PYRUN}
PyRun SSL dir: {PYRUN_SSL}
""".format(**{"sys": sys, **dc.asdict(config)}))

    config_json = {
        k: str(v) if isinstance(v, Path) else v
        for k, v in dc.asdict(config).items()
    }

    print(f"""
Config:
{json.dumps(config_json, sort_keys=True, indent=2)}
""")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", action="store_true")

    choices = []
    for k, v in PYVERSIONS.items():
        choices.append(k)
        choices.extend(v)
    parser.add_argument("version", choices=choices)
    parser.add_argument("--micro", "-m", type=int)
    parser.add_argument("-o", "--output",
        default="dist/egenix-pyrun-{package}-py{version}_{PYTHONUNICODE}-{PLATFORM}.tgz"
    )
    args = parser.parse_args()

    # pyver
    if not (pyrunversion := get_full_target_pythonversion(args.version, args.micro)):
        parser.error(f"canot find {args.version}.{args.micro}")

    args.config = config = Config(
        version=args.version,
        package=PACKAGEVERSION,
        dest=Path(""),
        PYTHONUNICODE="ucs4" if args.version.startswith("3.") else "ucs2",
        PLATFORM=get_platform(),
        PYRUNVERSION=pyrunversion,
        PYRUN_SSL=get_ssl(),
        PYTHONFULLVERSION=tuple([int(v) for v in pyrunversion.split(".")]),
    )

    config.dest = Path(args.output.format(**dc.asdict(config)))

    config.PYTHONVERSION = ".".join(str(v) for v in config.PYTHONFULLVERSION)
    config.PYTHONMAJORVERSION = ".".join(str(v) for v in config.PYTHONFULLVERSION[:2])
    config.PYTHONMINORVERSION = str(config.PYTHONFULLVERSION[-1])

    for key, value in dc.asdict(config).items():
        if isinstance(value, (str, Path)) and str(value).startswith("!"):
            value = type(value)(str(value)[1:].format(**dc.asdict(config)))
            setattr(config, key, value)

    return args


def main(args):
    if args.version:
        show_version(args.config)
        sys.exit()


if __name__ == "__main__":
    main(parse_args())
    
