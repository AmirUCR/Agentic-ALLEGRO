"""
tests/test_tools.py — Unit tests for ALLEGRO agent tool functions.

Run with: python -m pytest tests/ -v
"""

import csv
import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools import validate_inputs, generate_config, parse_results, dispatch


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_input(tmp_path):
    """Create a minimal valid ALLEGRO input directory + CSV."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()

    # Write two fake FASTA files
    species = ["S_cerevisiae_RAD51.fna", "K_lactis_RAD51.fna"]
    for fname in species:
        fasta = input_dir / fname
        fasta.write_text(f">gene1\nATGCATGCATGCATGCATGC\n>gene2\nTTTTCCCCGGGGAAAATTTT\n")

    # Write manifest CSV
    csv_path = tmp_path / "species.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["species_name", "ortho_file_name"])
        writer.writeheader()
        writer.writerow({"species_name": "S. cerevisiae", "ortho_file_name": "S_cerevisiae_RAD51.fna"})
        writer.writerow({"species_name": "K. lactis", "ortho_file_name": "K_lactis_RAD51.fna"})

    return {"input_dir": str(input_dir), "csv_path": str(csv_path), "tmp": tmp_path}


# ─────────────────────────────────────────────────────────────────────────────
# validate_inputs tests
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateInputs:
    def test_valid_inputs(self, tmp_input):
        result = validate_inputs(
            input_directory=tmp_input["input_dir"],
            input_species_path=tmp_input["csv_path"],
        )
        assert result["valid"] is True
        assert result["fasta_files_found"] == 2
        assert result["species_count"] == 2
        assert len(result["errors"]) == 0

    def test_missing_directory(self, tmp_path):
        result = validate_inputs(
            input_directory=str(tmp_path / "nonexistent"),
            input_species_path=str(tmp_path / "any.csv"),
        )
        assert result["valid"] is False
        assert any("does not exist" in e for e in result["errors"])

    def test_missing_csv(self, tmp_input):
        result = validate_inputs(
            input_directory=tmp_input["input_dir"],
            input_species_path=str(tmp_input["tmp"] / "nonexistent.csv"),
        )
        assert result["valid"] is False
        assert any("not found" in e for e in result["errors"])

    def test_wrong_column_name(self, tmp_input):
        result = validate_inputs(
            input_directory=tmp_input["input_dir"],
            input_species_path=tmp_input["csv_path"],
            input_species_path_column="wrong_column",
        )
        assert result["valid"] is False
        assert any("wrong_column" in e for e in result["errors"])

    def test_missing_fasta_file(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        # CSV references a file that doesn't exist
        csv_path = tmp_path / "species.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["ortho_file_name"])
            writer.writeheader()
            writer.writerow({"ortho_file_name": "missing.fna"})

        result = validate_inputs(
            input_directory=str(input_dir),
            input_species_path=str(csv_path),
        )
        assert result["valid"] is False
        assert any("missing.fna" in e for e in result["errors"])


# ─────────────────────────────────────────────────────────────────────────────
# generate_config tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateConfig:
    def test_writes_valid_yaml(self, tmp_input):
        import yaml
        config_path = str(tmp_input["tmp"] / "test_config.yaml")
        result = generate_config(
            experiment_name="test_run",
            input_directory=tmp_input["input_dir"],
            input_species_path=tmp_input["csv_path"],
            config_output_path=config_path,
        )
        assert Path(config_path).exists()
        with open(config_path) as f:
            loaded = yaml.safe_load(f)
        assert loaded["experiment_name"] == "test_run"
        assert loaded["pam"] == "NGG"
        assert loaded["track"] == "track_e"

    def test_custom_parameters(self, tmp_input):
        import yaml
        config_path = str(tmp_input["tmp"] / "custom_config.yaml")
        result = generate_config(
            experiment_name="cas12a_run",
            input_directory=tmp_input["input_dir"],
            input_species_path=tmp_input["csv_path"],
            pam="TTTV",
            multiplicity=2,
            scorer="ucrispr",
            beta=50,
            gc_min=0.3,
            gc_max=0.7,
            config_output_path=config_path,
        )
        with open(config_path) as f:
            loaded = yaml.safe_load(f)
        assert loaded["pam"] == "TTTV"
        assert loaded["multiplicity"] == 2
        assert loaded["scorer"] == "ucrispr"
        assert loaded["beta"] == 50
        assert loaded["gc_min"] == 0.3

    def test_cli_command_in_result(self, tmp_input):
        result = generate_config(
            experiment_name="my_exp",
            input_directory=tmp_input["input_dir"],
            input_species_path=tmp_input["csv_path"],
        )
        assert "allegro" in result["cli_command"]
        assert "my_exp" in result["cli_command"]

    def test_default_patterns_to_exclude(self, tmp_input):
        import yaml
        config_path = str(tmp_input["tmp"] / "default_config.yaml")
        generate_config(
            experiment_name="test",
            input_directory=tmp_input["input_dir"],
            input_species_path=tmp_input["csv_path"],
            config_output_path=config_path,
        )
        with open(config_path) as f:
            loaded = yaml.safe_load(f)
        assert "TTTT" in loaded["patterns_to_exclude"]


# ─────────────────────────────────────────────────────────────────────────────
# parse_results tests
# ─────────────────────────────────────────────────────────────────────────────

class TestParseResults:
    def test_parses_output_csv(self, tmp_path):
        # Create a fake ALLEGRO output
        exp_name = "my_experiment"
        output_dir = tmp_path / "output" / exp_name
        output_dir.mkdir(parents=True)
        csv_path = output_dir / f"{exp_name}.csv"

        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["sgrna_sequence", "species_name", "score", "cluster"]
            )
            writer.writeheader()
            for i in range(5):
                writer.writerow({
                    "sgrna_sequence": f"ATGCATGCATGCATGCATG{i}",
                    "species_name": f"species_{i % 3}",
                    "score": str(70 + i),
                    "cluster": str(i // 2),
                })

        result = parse_results(
            output_directory=str(tmp_path / "output"),
            experiment_name=exp_name,
        )
        assert result["success"] is True
        assert result["num_guides"] == 5
        assert result["scores"]["avg"] == pytest.approx(72.0)

    def test_missing_output(self, tmp_path):
        result = parse_results(
            output_directory=str(tmp_path / "nonexistent"),
            experiment_name="ghost_run",
        )
        assert result["success"] is False
        assert "error" in result


# ─────────────────────────────────────────────────────────────────────────────
# dispatch tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDispatch:
    def test_dispatch_valid_tool(self, tmp_input):
        result_str = dispatch("validate_inputs", {
            "input_directory": tmp_input["input_dir"],
            "input_species_path": tmp_input["csv_path"],
        })
        result = json.loads(result_str)
        assert result["valid"] is True

    def test_dispatch_unknown_tool(self, tmp_input):
        result_str = dispatch("nonexistent_tool", {})
        result = json.loads(result_str)
        assert "error" in result
        assert "Unknown tool" in result["error"]

    def test_dispatch_bad_arguments(self, tmp_input):
        result_str = dispatch("validate_inputs", {"bad_arg": "oops"})
        result = json.loads(result_str)
        assert "error" in result