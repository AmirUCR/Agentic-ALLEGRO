"""
tools.py — ALLEGRO agent tool implementations + Anthropic tool schemas.

Each function here corresponds to one tool Claude can call. The TOOL_DEFINITIONS
list at the bottom defines the JSON schemas passed to the Anthropic API.
"""

import os
import csv
import subprocess
import tempfile
import yaml
import json
from pathlib import Path
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1: validate_inputs
# ─────────────────────────────────────────────────────────────────────────────

def validate_inputs(
    input_directory: str,
    input_species_path: str,
    input_species_path_column: str = "ortho_file_name",
) -> dict[str, Any]:
    """
    Validates that the input directory and species CSV are well-formed for ALLEGRO.
    Returns a dict with 'valid' (bool), 'errors' (list), and 'summary' (str).
    """
    errors = []
    warnings = []

    # 1. Check input directory exists
    input_dir = Path(input_directory)
    if not input_dir.exists():
        errors.append(f"Input directory does not exist: {input_directory}")
        return {"valid": False, "errors": errors, "warnings": warnings, "summary": "Input directory not found."}

    # 2. Check species CSV exists
    csv_path = Path(input_species_path)
    if not csv_path.exists():
        errors.append(f"Species CSV not found: {input_species_path}")
        return {"valid": False, "errors": errors, "warnings": warnings, "summary": "Species CSV not found."}

    # 3. Parse CSV and check referenced files
    fasta_files_found = []
    fasta_files_missing = []
    species_names = []

    try:
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []

            if input_species_path_column not in fieldnames:
                errors.append(
                    f"Column '{input_species_path_column}' not found in CSV. "
                    f"Available columns: {fieldnames}"
                )
                return {"valid": False, "errors": errors, "warnings": warnings, "summary": "CSV column mismatch."}

            rows = list(reader)
            if not rows:
                errors.append("Species CSV is empty (no data rows).")
                return {"valid": False, "errors": errors, "warnings": warnings, "summary": "Empty CSV."}

            for row in rows:
                fname = row[input_species_path_column].strip()
                species_names.append(fname)
                fasta_path = input_dir / fname
                if fasta_path.exists():
                    fasta_files_found.append(str(fasta_path))
                    # Basic FASTA check: first line should start with '>'
                    with open(fasta_path) as ff:
                        first_line = ff.readline().strip()
                        if not first_line.startswith(">"):
                            warnings.append(f"{fname} may not be a valid FASTA (first line: '{first_line[:40]}')")
                else:
                    fasta_files_missing.append(fname)

    except Exception as e:
        errors.append(f"Failed to parse CSV: {e}")
        return {"valid": False, "errors": errors, "warnings": warnings, "summary": "CSV parse error."}

    if fasta_files_missing:
        errors.append(
            f"{len(fasta_files_missing)} FASTA file(s) listed in CSV not found in {input_directory}: "
            + ", ".join(fasta_files_missing[:5])
            + ("..." if len(fasta_files_missing) > 5 else "")
        )

    valid = len(errors) == 0
    summary = (
        f"Found {len(fasta_files_found)}/{len(species_names)} FASTA files. "
        + (f"{len(warnings)} warning(s)." if warnings else "All files look valid.")
    )

    return {
        "valid": valid,
        "errors": errors,
        "warnings": warnings,
        "summary": summary,
        "species_count": len(species_names),
        "fasta_files_found": len(fasta_files_found),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2: generate_config
# ─────────────────────────────────────────────────────────────────────────────

def generate_config(
    experiment_name: str,
    input_directory: str,
    input_species_path: str,
    output_directory: str = "data/output",
    input_species_path_column: str = "ortho_file_name",
    pam: str = "NGG",
    protospacer_length: int = 20,
    track: str = "track_e",
    multiplicity: int = 1,
    scorer: str = "dummy",
    beta: int = 0,
    filter_by_gc: bool = True,
    gc_min: float = 0.4,
    gc_max: float = 0.6,
    guide_score_threshold: int = 0,
    patterns_to_exclude: list[str] | None = None,
    output_offtargets: bool = False,
    preclustering: bool = False,
    postclustering: bool = False,
    early_stopping_patience: int = 60,
    config_output_path: str = "allegro_config.yaml",
) -> dict[str, Any]:
    """
    Generates a valid ALLEGRO config.yaml from the given parameters.
    Returns the path to the written config and a human-readable summary.
    """
    if patterns_to_exclude is None:
        patterns_to_exclude = ["TTTT"]

    config = {
        "experiment_name": experiment_name,
        "input_directory": input_directory,
        "input_species_path": input_species_path,
        "input_species_path_column": input_species_path_column,
        "output_directory": output_directory,
        "pam": pam,
        "protospacer_length": protospacer_length,
        "track": track,
        "multiplicity": multiplicity,
        "scorer": scorer,
        "beta": beta,
        "filter_by_gc": filter_by_gc,
        "gc_min": gc_min,
        "gc_max": gc_max,
        "guide_score_threshold": guide_score_threshold,
        "patterns_to_exclude": patterns_to_exclude,
        "output_offtargets": output_offtargets,
        "report_up_to_n_mismatches": 1,
        "preclustering": preclustering,
        "postclustering": postclustering,
        "seed_region_is_n_upstream_of_pam": 12,
        "mismatches_allowed_after_seed_region": 1,
        "early_stopping_patience": early_stopping_patience,
        "mp_threshold": 0,
        "enable_solver_diagnostics": True,
        "align_solution_to_input": True,  # Requires Bowtie
    }

    config_path = Path(config_output_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    # Build a CLI command string for transparency
    cli_cmd = (
        f"allegro -c {config_output_path} "
        f"-n {experiment_name} "
        f"-id {input_directory} "
        f"-isp {input_species_path}"
    )

    summary = (
        f"Config written to: {config_output_path}\n"
        f"Experiment: {experiment_name}\n"
        f"PAM: {pam} | Track: {track} | Multiplicity: {multiplicity}\n"
        f"Scorer: {scorer} | Beta: {beta or 'disabled (find minimum)'}\n"
        f"GC filter: {gc_min}–{gc_max} | Off-targets: {output_offtargets}\n"
        f"Equivalent CLI: {cli_cmd}"
    )

    return {
        "config_path": str(config_path),
        "config": config,
        "cli_command": cli_cmd,
        "summary": summary,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool 3: run_allegro
# ─────────────────────────────────────────────────────────────────────────────

def run_allegro(
    config_path: str,
    allegro_executable: str = "allegro",
    timeout_seconds: int = 600,
) -> dict[str, Any]:
    """
    Runs ALLEGRO as a subprocess using the given config file.
    Returns stdout, stderr, return code, and success status.
    """
    if not Path(config_path).exists():
        return {
            "success": False,
            "error": f"Config file not found: {config_path}",
            "stdout": "",
            "stderr": "",
            "returncode": -1,
        }

    cmd = [allegro_executable, "--config", config_path]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

        success = result.returncode == 0

        return {
            "success": success,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "error": None if success else f"ALLEGRO exited with code {result.returncode}",
        }

    except FileNotFoundError:
        return {
            "success": False,
            "error": (
                f"ALLEGRO executable '{allegro_executable}' not found. "
                "Please install ALLEGRO and ensure it's on your PATH "
                "(pip install allegro, or build from source)."
            ),
            "stdout": "",
            "stderr": "",
            "returncode": -1,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"ALLEGRO timed out after {timeout_seconds}s.",
            "stdout": "",
            "stderr": "",
            "returncode": -1,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Tool 4: parse_results
# ─────────────────────────────────────────────────────────────────────────────

def parse_results(
    output_directory: str,
    experiment_name: str,
) -> dict[str, Any]:
    """
    Parses ALLEGRO's output CSV and returns a structured summary of the sgRNA library.
    """
    output_dir = Path(output_directory) / experiment_name
    csv_path = output_dir / f"{experiment_name}.csv"

    if not csv_path.exists():
        # Try finding any CSV in the output directory
        candidates = list(output_dir.glob("*.csv")) if output_dir.exists() else []
        if candidates:
            csv_path = candidates[0]
        else:
            return {
                "success": False,
                "error": f"No output CSV found at {csv_path}. Has ALLEGRO been run successfully?",
            }

    try:
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fieldnames = reader.fieldnames or []

        if not rows:
            return {"success": False, "error": "Output CSV is empty."}

        num_guides = len(rows)

        # Score statistics (if scorer != dummy)
        scores = []
        score_col = next((c for c in fieldnames if "score" in c.lower()), None)
        if score_col:
            scores = [float(r[score_col]) for r in rows if r.get(score_col)]

        # Coverage: species/targets hit
        species_col = next((c for c in fieldnames if "species" in c.lower()), None)
        species_covered = set()
        if species_col:
            species_covered = {r[species_col] for r in rows if r.get(species_col)}

        # Cluster info
        cluster_col = next((c for c in fieldnames if "cluster" in c.lower()), None)
        num_clusters = len({r[cluster_col] for r in rows if r.get(cluster_col)}) if cluster_col else None

        # Build guide list (first 10 for preview)
        guide_col = next(
            (c for c in fieldnames if any(k in c.lower() for k in ["guide", "sgrna", "seq", "protospacer"])),
            fieldnames[0] if fieldnames else None,
        )
        guide_preview = [r.get(guide_col, "") for r in rows[:10]] if guide_col else []

        summary_parts = [
            f"Library size: {num_guides} sgRNAs",
            f"Output file: {csv_path}",
        ]
        if species_covered:
            summary_parts.append(f"Species/targets covered: {len(species_covered)}")
        if scores:
            avg = sum(scores) / len(scores)
            summary_parts.append(f"Score range: {min(scores):.1f}–{max(scores):.1f} (avg {avg:.1f})")
        if num_clusters is not None:
            summary_parts.append(f"Clusters: {num_clusters}")

        return {
            "success": True,
            "csv_path": str(csv_path),
            "num_guides": num_guides,
            "columns": fieldnames,
            "scores": {"min": min(scores), "max": max(scores), "avg": sum(scores)/len(scores)} if scores else None,
            "species_covered": len(species_covered),
            "num_clusters": num_clusters,
            "guide_preview": guide_preview,
            "summary": "\n".join(summary_parts),
            "all_rows": rows,  # Full data available for further analysis
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to parse output CSV: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# Tool dispatcher — called by the agent loop
# ─────────────────────────────────────────────────────────────────────────────

TOOL_FUNCTIONS = {
    "validate_inputs": validate_inputs,
    "generate_config": generate_config,
    "run_allegro": run_allegro,
    "parse_results": parse_results,
}


def dispatch(tool_name: str, tool_input: dict) -> str:
    """Execute a tool by name and return its result as a JSON string."""
    fn = TOOL_FUNCTIONS.get(tool_name)
    if fn is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    try:
        result = fn(**tool_input)
        return json.dumps(result, indent=2)
    except TypeError as e:
        return json.dumps({"error": f"Invalid arguments for {tool_name}: {e}"})


# ─────────────────────────────────────────────────────────────────────────────
# Anthropic tool schemas
# ─────────────────────────────────────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "validate_inputs",
        "description": (
            "Validate that ALLEGRO input files are well-formed before running. "
            "Checks that the input directory exists, the species CSV is parseable, "
            "the specified file column exists, and all referenced FASTA files are present. "
            "Always call this before generate_config or run_allegro."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "input_directory": {
                    "type": "string",
                    "description": "Path to directory containing FASTA (.fna/.fa) genome files.",
                },
                "input_species_path": {
                    "type": "string",
                    "description": "Path to the species manifest CSV file.",
                },
                "input_species_path_column": {
                    "type": "string",
                    "description": "Column name in the CSV that contains FASTA filenames. Default: 'ortho_file_name'.",
                    "default": "ortho_file_name",
                },
            },
            "required": ["input_directory", "input_species_path"],
        },
    },
    {
        "name": "generate_config",
        "description": (
            "Generate a valid ALLEGRO config.yaml from user-specified parameters. "
            "Translates research intent (e.g., 'minimal library for SpCas9 across 50 yeast species') "
            "into the correct ALLEGRO settings. Call after validate_inputs succeeds."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "experiment_name": {"type": "string", "description": "Short name for this run (used in output filenames)."},
                "input_directory": {"type": "string", "description": "Path to FASTA files directory."},
                "input_species_path": {"type": "string", "description": "Path to species manifest CSV."},
                "output_directory": {"type": "string", "description": "Where to write results. Default: 'data/output'.", "default": "data/output"},
                "input_species_path_column": {"type": "string", "description": "CSV column naming FASTA files.", "default": "ortho_file_name"},
                "pam": {"type": "string", "description": "PAM sequence. 'NGG' for SpCas9, 'TTTV' for Cas12a.", "default": "NGG"},
                "protospacer_length": {"type": "integer", "description": "Guide RNA length in nt. Default: 20.", "default": 20},
                "track": {
                    "type": "string",
                    "enum": ["track_e", "track_a"],
                    "description": "track_e: each gene must be hit ≥multiplicity times. track_a: each species must be hit ≥multiplicity times anywhere.",
                    "default": "track_e",
                },
                "multiplicity": {"type": "integer", "description": "Minimum number of times each target must be hit. Default: 1.", "default": 1},
                "scorer": {
                    "type": "string",
                    "enum": ["dummy", "ucrispr"],
                    "description": "dummy: minimize library size, ignore efficacy. ucrispr: score guides by predicted cutting efficiency (requires beta > 0).",
                    "default": "dummy",
                },
                "beta": {"type": "integer", "description": "Max library size budget. 0 = find minimum size (ignores scores). Set to number of species/genes for scored runs.", "default": 0},
                "filter_by_gc": {"type": "boolean", "description": "Filter guides outside GC range. Default: true.", "default": True},
                "gc_min": {"type": "number", "description": "Minimum GC fraction (0–1). Default: 0.4.", "default": 0.4},
                "gc_max": {"type": "number", "description": "Maximum GC fraction (0–1). Default: 0.6.", "default": 0.6},
                "guide_score_threshold": {"type": "integer", "description": "Discard guides below this ucrispr score. Only used with scorer=ucrispr.", "default": 0},
                "patterns_to_exclude": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "IUPAC patterns to exclude from guides (e.g. ['TTTT'] excludes poly-T).",
                },
                "output_offtargets": {"type": "boolean", "description": "Report off-targets (requires Bowtie v1). Default: false.", "default": False},
                "preclustering": {"type": "boolean", "description": "Enable preclustering to reduce library size (requires Bowtie v1). Default: false.", "default": False},
                "postclustering": {"type": "boolean", "description": "Cluster similar guides in output (requires Bowtie v1). Default: false.", "default": False},
                "early_stopping_patience": {"type": "integer", "description": "ILP solver timeout in seconds. Default: 60.", "default": 60},
                "config_output_path": {"type": "string", "description": "Where to write the config YAML. Default: 'allegro_config.yaml'.", "default": "allegro_config.yaml"},
            },
            "required": ["experiment_name", "input_directory", "input_species_path"],
        },
    },
    {
        "name": "run_allegro",
        "description": (
            "Execute ALLEGRO using a config file generated by generate_config. "
            "Runs the ALLEGRO CLI as a subprocess and captures all output. "
            "Call after generate_config returns successfully."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "config_path": {"type": "string", "description": "Path to the ALLEGRO config.yaml to use."},
                "allegro_executable": {"type": "string", "description": "Name or path of the ALLEGRO executable. Default: 'allegro'.", "default": "allegro"},
                "timeout_seconds": {"type": "integer", "description": "Max seconds to wait for ALLEGRO to finish. Default: 600.", "default": 600},
            },
            "required": ["config_path"],
        },
    },
    {
        "name": "parse_results",
        "description": (
            "Read and summarize ALLEGRO's output CSV after a successful run. "
            "Returns library size, guide sequences, score statistics, species coverage, "
            "and cluster info. Call after run_allegro returns success=true."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "output_directory": {"type": "string", "description": "Output directory used in the ALLEGRO run."},
                "experiment_name": {"type": "string", "description": "Experiment name used in the ALLEGRO run."},
            },
            "required": ["output_directory", "experiment_name"],
        },
    },
]