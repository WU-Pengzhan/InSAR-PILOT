"""Headless NISAR AOI discovery, download, and ISCE3 InSAR commands."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, time, timezone
from pathlib import Path

from insar_pilot.application.nisar_acquisition import NisarAcquisitionService
from insar_pilot.backends.isce3 import (
    NisarInsarValidator,
    NisarIsce3RuntimeProbe,
    NisarRifgPlanBuilder,
    NisarRifgRunner,
    NisarRifgValidator,
)
from insar_pilot.backends.openseppo import OpenSeppoSubsetPlanBuilder, OpenSeppoSubsetRunner
from insar_pilot.domain.local_data import AssetRef
from insar_pilot.domain.task_runtime import RuntimeProfile
from insar_pilot.download.credentials import load_earthdata_credentials
from insar_pilot.download.network import NetworkConfig
from insar_pilot.providers.local import NisarRslcReader, ReaderContext


class NisarCliError(RuntimeError):
    pass


def _parse_time(text: str, *, end_of_day: bool = False) -> datetime:
    value = text.strip()
    try:
        if "T" not in value:
            day = datetime.fromisoformat(value).date()
            return datetime.combine(day, time.max if end_of_day else time.min, tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid ISO-8601 time: {text}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _profile(args: argparse.Namespace) -> RuntimeProfile:
    settings = {"python_executable": str(Path(args.python).expanduser())}
    if getattr(args, "proj_data", ""):
        settings["proj_data"] = str(Path(args.proj_data).expanduser())
    return RuntimeProfile("nisar-local", "isce3.nisar_rifg", settings)


def _credentials() -> tuple[str, str]:
    credentials = load_earthdata_credentials()
    if credentials is None:
        raise NisarCliError(
            "Earthdata credentials were not found. Set EARTHDATA_USERNAME and "
            "EARTHDATA_PASSWORD for this shell, or configure ~/.netrc."
        )
    return credentials.username, credentials.password


def _cmd_search(args: argparse.Namespace) -> int:
    service = NisarAcquisitionService()
    manifest = service.search_aoi(
        args.aoi,
        _parse_time(args.start),
        _parse_time(args.end, end_of_day=True),
        orbit_direction=args.direction or None,
        path_number=args.path,
        frame=args.frame,
        polarizations=tuple(args.polarization),
        frequency_bands=tuple(args.frequency),
        production_configuration=args.production_configuration,
        page_size=args.limit,
    )
    target = service.save_manifest(manifest, args.manifest)
    print(f"Found {len(manifest.products)} NISAR RSLC granule(s); manifest: {target}")
    for product in manifest.products:
        frame = product.provider_metadata.get("frame_number", "")
        size_gib = float(product.size_bytes or 0) / (1024**3)
        print(
            f"{product.remote_product_id}\tpath={product.relative_orbit or ''}\t"
            f"frame={frame}\t{size_gib:.2f} GiB"
        )
    return 0


def _cmd_download(args: argparse.Namespace) -> int:
    service = NisarAcquisitionService()
    manifest = service.load_manifest(args.manifest)
    tasks = service.create_download_tasks(manifest, args.output, product_ids=tuple(args.product))
    if args.dry_run:
        for task in tasks:
            print(f"{task.scene.scene_id}\t{task.local_path}\t{task.url}")
        return 0
    username, password = _credentials()
    results = service.download(
        manifest,
        args.output,
        username=username,
        password=password,
        product_ids=tuple(args.product),
    )
    for result in results:
        print(f"{result.status}\t{result.scene.scene_id}\t{result.local_path}\t{result.message}")
    return 0 if results and all(item.status in {"completed", "skipped"} for item in results) else 1


def _cmd_probe_download(args: argparse.Namespace) -> int:
    service = NisarAcquisitionService()
    manifest = service.load_manifest(args.manifest)
    products = manifest.products
    if args.product:
        products = tuple(item for item in products if item.remote_product_id == args.product)
    if not products:
        raise NisarCliError("No matching product exists in the manifest.")
    username, password = _credentials()
    report = service.probe_download_access(products[0], username=username, password=password)
    print(json.dumps(report.__dict__, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.accessible else 1


def _cmd_probe_runtime(args: argparse.Namespace) -> int:
    report = NisarIsce3RuntimeProbe().probe(_profile(args))
    print(json.dumps(report.__dict__, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.available else 1


def _cmd_subset(args: argparse.Namespace) -> int:
    inputs = tuple(args.input or ())
    if args.manifest:
        manifest = NisarAcquisitionService().load_manifest(args.manifest)
        selected = manifest.products
        if args.product:
            wanted = set(args.product)
            selected = tuple(item for item in selected if item.remote_product_id in wanted)
            missing = wanted.difference(item.remote_product_id for item in selected)
            if missing:
                raise NisarCliError(
                    f"Manifest does not contain NISAR products: {', '.join(sorted(missing))}"
                )
        missing_urls = tuple(item.remote_product_id for item in selected if not item.download_url)
        if missing_urls:
            raise NisarCliError(f"NISAR product has no remote URL: {missing_urls[0]}")
        inputs = tuple(str(item.download_url) for item in selected)
    plan = OpenSeppoSubsetPlanBuilder().build(
        inputs,
        args.aoi,
        args.output,
        executable=args.executable,
        frequency=args.frequency,
        polarizations=tuple(args.polarization),
        all_frequencies=args.all_frequencies,
        min_height=args.min_height,
        max_height=args.max_height,
        quicklook=args.quicklook,
        cache=args.cache or None,
        keep_cached=args.keep_cached,
        verbose=args.verbose,
    )
    if args.plan_only:
        print(" ".join(plan.command))
        return 0
    report = OpenSeppoSubsetRunner().run(
        plan,
        timeout_seconds=args.timeout,
        network=NetworkConfig(mode=args.network_mode),
    )
    print(json.dumps(report.__dict__, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.succeeded else 1


def _run_insar(args: argparse.Namespace, *, product_type: str) -> int:
    reader = NisarRslcReader()
    context = ReaderContext()
    reference = reader.read(AssetRef(str(Path(args.reference).expanduser()), "source_product"), context)
    secondary = reader.read(AssetRef(str(Path(args.secondary).expanduser()), "source_product"), context)
    profile = _profile(args)
    builder = NisarRifgPlanBuilder()
    plan = builder.build(
        reference,
        secondary,
        AssetRef(str(Path(args.dem).expanduser()), "prepared_dem"),
        output_dir=args.output,
        template_path=args.template,
        profile=profile,
        frequency=args.frequency,
        polarization=args.polarization,
        product_type=product_type,
        geocode_bounds=tuple(args.geocode_bounds) if args.geocode_bounds else None,
    )
    builder.write_runconfig(plan, replace_existing=args.replace_runconfig)
    if args.plan_only:
        print(plan.runconfig_path)
        print(" ".join(plan.command))
        return 0
    report = NisarRifgRunner().run(
        plan,
        profile,
        frequency=args.frequency,
        polarization=args.polarization,
        timeout_seconds=args.timeout,
    )
    payload = dict(report.__dict__)
    payload["output_product"] = report.output_product.to_dict()
    payload["validation"] = report.validation.__dict__ if report.validation is not None else None
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.succeeded else 1


def _cmd_run_rifg(args: argparse.Namespace) -> int:
    return _run_insar(args, product_type="RIFG")


def _cmd_run_insar(args: argparse.Namespace) -> int:
    return _run_insar(args, product_type=args.product_type)


def _cmd_validate_rifg(args: argparse.Namespace) -> int:
    report = NisarRifgValidator().validate(
        args.product,
        frequency=args.frequency,
        polarization=args.polarization,
    )
    print(json.dumps(report.__dict__, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.valid else 1


def _cmd_validate_insar(args: argparse.Namespace) -> int:
    report = NisarInsarValidator().validate(
        args.product,
        product_type=args.product_type,
        frequency=args.frequency,
        polarization=args.polarization,
    )
    print(json.dumps(report.__dict__, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.valid else 1


def _add_runtime_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--python", default=sys.executable, help="Python executable containing ISCE3/nisar workflows.")
    parser.add_argument("--proj-data", default=os.environ.get("PROJ_DATA", ""))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="insar-pilot-nisar", description="NISAR RSLC backend utilities.")
    commands = parser.add_subparsers(dest="command", required=True)

    search = commands.add_parser("search", help="Find complete ASF RSLC granules intersecting a KML/SHP AOI.")
    search.add_argument("--aoi", required=True)
    search.add_argument("--start", required=True)
    search.add_argument("--end", required=True)
    search.add_argument("--manifest", required=True)
    search.add_argument("--direction", choices=("ASCENDING", "DESCENDING"), default="")
    search.add_argument("--path", type=int)
    search.add_argument("--frame", type=int)
    search.add_argument("--frequency", action="append", choices=("A", "B"), default=[])
    search.add_argument("--polarization", action="append", choices=("HH", "HV", "VV", "VH"), default=[])
    search.add_argument("--production-configuration", choices=("PR", "UR"), default="PR")
    search.add_argument("--limit", type=int, default=100)
    search.set_defaults(func=_cmd_search)

    download = commands.add_parser("download", help="Download selected RSLC HDF5 granules from a manifest.")
    download.add_argument("--manifest", required=True)
    download.add_argument("--output", required=True)
    download.add_argument("--product", action="append", default=[])
    download.add_argument("--dry-run", action="store_true")
    download.set_defaults(func=_cmd_download)

    access = commands.add_parser("probe-download", help="Authenticate and read only the remote HDF5 signature.")
    access.add_argument("--manifest", required=True)
    access.add_argument("--product", default="")
    access.set_defaults(func=_cmd_probe_download)

    runtime = commands.add_parser("probe-runtime", help="Probe ISCE3 workflow and GDAL/HDF5 compatibility.")
    _add_runtime_options(runtime)
    runtime.set_defaults(func=_cmd_probe_runtime)

    subset = commands.add_parser("subset", help="Create ISCE3-readable AOI RSLC subsets with openSEPPO.")
    subset_inputs = subset.add_mutually_exclusive_group(required=True)
    subset_inputs.add_argument("--input", action="append")
    subset_inputs.add_argument("--manifest")
    subset.add_argument("--product", action="append", default=[])
    subset.add_argument("--aoi", required=True)
    subset.add_argument("--output", required=True)
    subset.add_argument("--executable", required=True)
    subset.add_argument("--frequency", choices=("A", "B"), default="A")
    subset.add_argument("--polarization", action="append", choices=("HH", "HV", "VV", "VH"), default=[])
    subset.add_argument("--all-frequencies", action="store_true")
    subset.add_argument("--min-height", type=float)
    subset.add_argument("--max-height", type=float)
    subset.add_argument("--quicklook", action="store_true")
    subset.add_argument(
        "--cache",
        default="",
        help="Explicitly cache each complete remote HDF5 before subsetting; disabled by default.",
    )
    subset.add_argument("--keep-cached", action="store_true")
    subset.add_argument("--verbose", action="store_true", help="Record openSEPPO terrain and window details.")
    subset.add_argument(
        "--network-mode",
        choices=("direct", "environment"),
        default="direct",
        help="Direct ignores WSL proxy variables; environment explicitly inherits them.",
    )
    subset.add_argument("--plan-only", action="store_true")
    subset.add_argument("--timeout", type=float)
    subset.set_defaults(func=_cmd_subset)

    run = commands.add_parser("run-rifg", help="Build a pair runconfig, run ISCE3, and validate RIFG output.")
    run.add_argument("--reference", required=True)
    run.add_argument("--secondary", required=True)
    run.add_argument("--dem", required=True)
    run.add_argument("--template", required=True)
    run.add_argument("--output", required=True)
    run.add_argument("--frequency", choices=("A", "B"), required=True)
    run.add_argument("--polarization", choices=("HH", "HV", "VV", "VH"), required=True)
    run.add_argument("--plan-only", action="store_true")
    run.add_argument("--replace-runconfig", action="store_true")
    run.add_argument("--timeout", type=float)
    run.add_argument(
        "--geocode-bounds",
        type=float,
        nargs=4,
        metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
        help="Optional projected geocode bounds; primarily used by GUNW.",
    )
    _add_runtime_options(run)
    run.set_defaults(func=_cmd_run_rifg)

    run_all = commands.add_parser(
        "run-insar", help="Build, run, and validate an ISCE3 RIFG, RUNW, or GUNW product."
    )
    run_all.add_argument("--product-type", choices=("RIFG", "RUNW", "GUNW"), required=True)
    run_all.add_argument("--reference", required=True)
    run_all.add_argument("--secondary", required=True)
    run_all.add_argument("--dem", required=True)
    run_all.add_argument("--template", required=True)
    run_all.add_argument("--output", required=True)
    run_all.add_argument("--frequency", choices=("A", "B"), required=True)
    run_all.add_argument("--polarization", choices=("HH", "HV", "VV", "VH"), required=True)
    run_all.add_argument("--plan-only", action="store_true")
    run_all.add_argument("--replace-runconfig", action="store_true")
    run_all.add_argument("--timeout", type=float)
    run_all.add_argument(
        "--geocode-bounds",
        type=float,
        nargs=4,
        metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
        help="Projected bounds ordered as left, top, right, bottom.",
    )
    _add_runtime_options(run_all)
    run_all.set_defaults(func=_cmd_run_insar)

    validate = commands.add_parser("validate-rifg", help="Validate an existing RIFG without loading full rasters.")
    validate.add_argument("--product", required=True)
    validate.add_argument("--frequency", choices=("A", "B"), required=True)
    validate.add_argument("--polarization", choices=("HH", "HV", "VV", "VH"), required=True)
    validate.set_defaults(func=_cmd_validate_rifg)

    validate_all = commands.add_parser("validate-insar", help="Validate an existing RIFG/RUNW/GUNW product.")
    validate_all.add_argument("--product", required=True)
    validate_all.add_argument("--product-type", choices=("RIFG", "RUNW", "GUNW"), required=True)
    validate_all.add_argument("--frequency", choices=("A", "B"), required=True)
    validate_all.add_argument("--polarization", choices=("HH", "HV", "VV", "VH"), required=True)
    validate_all.set_defaults(func=_cmd_validate_insar)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (NisarCliError, OSError, RuntimeError, TypeError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
