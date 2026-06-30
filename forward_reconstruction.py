"""
Forward reconstruction evaluation module.

Evaluates sound law systems defined in YAML format against cognate data
from a SQLite database. Provides metrics and error reports via an API.

YAML files should be placed in the forward_reconstruction/ directory and
include a 'name' field. Leaf nodes in the tree should use glottocodes
that resolve to language IDs in the database.
"""

import argparse
import difflib
import glob
import os
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import yaml

# Default paths
DEFAULT_RECONSTRUCTION_DIR = Path(__file__).parent / "forward_reconstruction"
DEFAULT_DB_PATH = Path(__file__).parent / "db" / "borderlands.sqlite3"


@dataclass
class SoundLaw:
    """A sound law with source, target, and context constraints."""
    id: str
    source: str
    target: str
    left: str
    right: str

    def to_function(self) -> Callable[[str], str]:
        """Convert this law to a string transformation function."""
        left = self.left or ""
        right = self.right or ""
        source = self.source or ""
        target = self.target or ""
        pattern = f"(?<={left})({source})(?={right})"
        return lambda x: re.sub(pattern, target, x)


@dataclass
class TreeNode:
    """A node in the phylogenetic tree."""
    child: str
    laws: list[str]


@dataclass
class ForwardReconstruction:
    """A forward reconstruction system with laws and tree."""
    name: str
    laws: dict[str, SoundLaw]
    tree: dict[str, list[TreeNode]]

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "ForwardReconstruction":
        """Parse a forward reconstruction from YAML string.

        The YAML must include a 'name' field at the top level.

        Laws can be specified in two formats:

        Compact list format (recommended):
            laws:
              d-to-r: ["d", "r", "", ""]
              final-k: ["", "k", "[iu]", "\\Z"]

        Verbose object format:
            laws:
              d-to-r:
                source: "d"
                target: "r"
                left: ""
                right: ""

        Leaf nodes in the tree should use glottocodes (e.g., phad1238)
        that will be resolved to language IDs in the database.
        """
        data = yaml.safe_load(yaml_str)

        name = data.get("name", "unnamed")

        laws = {}
        for law_id, law_data in data.get("laws", {}).items():
            if isinstance(law_data, list):
                # Compact format: [source, target, left, right]
                laws[law_id] = SoundLaw(
                    id=law_id,
                    source=law_data[0] if len(law_data) > 0 else "",
                    target=law_data[1] if len(law_data) > 1 else "",
                    left=law_data[2] if len(law_data) > 2 else "",
                    right=law_data[3] if len(law_data) > 3 else "",
                )
            else:
                # Verbose object format
                laws[law_id] = SoundLaw(
                    id=law_id,
                    source=law_data.get("source", ""),
                    target=law_data.get("target", ""),
                    left=law_data.get("left", ""),
                    right=law_data.get("right", ""),
                )

        tree = {}
        for parent, children in data.get("tree", {}).items():
            tree[parent] = [
                TreeNode(child=c["child"], laws=c.get("laws", []))
                for c in children
            ]

        return cls(name=name, laws=laws, tree=tree)

    def apply_laws(self, word: str, root: str = "ROOT") -> dict[str, str]:
        """Apply the tree of sound laws to a proto-form.

        Returns a dict mapping leaf node names to predicted reflexes.
        """
        # Build law functions
        law_funcs = {lid: law.to_function() for lid, law in self.laws.items()}

        results = {}
        stack = [(root, word)]

        while stack:
            label, form = stack.pop()

            if label not in self.tree:
                # Leaf node - record result
                results[label] = form
                continue

            for node in self.tree[label]:
                new_form = form
                for law_id in node.laws:
                    if law_id in law_funcs:
                        new_form = law_funcs[law_id](new_form)
                stack.append((node.child, new_form))

        return results

    def get_leaf_languages(self) -> set[str]:
        """Return the set of leaf node names (attested languages)."""
        all_children = set()
        for children in self.tree.values():
            for node in children:
                all_children.add(node.child)
        return all_children - set(self.tree.keys())

    def count_law_references(self) -> int:
        """Count total law references across all tree nodes."""
        return sum(
            len(node.laws)
            for nodes in self.tree.values()
            for node in nodes
        )


@dataclass
class Mismatch:
    """A single mismatch between hypothesis and reference."""
    language: str
    hypothesis: str
    reference: str

    def format_diff(self, use_color: bool = True) -> str:
        """Return a colorized character-level diff string."""
        RED = "\033[31m" if use_color else ""
        YELLOW = "\033[33m" if use_color else ""
        RESET = "\033[0m" if use_color else ""

        matcher = difflib.SequenceMatcher(None, self.hypothesis, self.reference)
        hyp_parts: list[str] = []
        ref_parts: list[str] = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                hyp_parts.append(self.hypothesis[i1:i2])
                ref_parts.append(self.reference[j1:j2])
            elif tag == "replace":
                hyp_parts.append(f"{YELLOW}{self.hypothesis[i1:i2]}{RESET}")
                ref_parts.append(f"{YELLOW}{self.reference[j1:j2]}{RESET}")
            elif tag == "delete":
                hyp_parts.append(f"{RED}{self.hypothesis[i1:i2]}{RESET}")
            elif tag == "insert":
                ref_parts.append(f"{RED}{self.reference[j1:j2]}{RESET}")

        lines = [
            f"  AssertionError: assert {self.hypothesis!r} == {self.reference!r}",
            f"    - {''.join(ref_parts)}  (expected)",
            f"    + {''.join(hyp_parts)}  (got)",
        ]
        return "\n".join(lines)


@dataclass
class CognateSetResult:
    """Evaluation result for a single cognate set."""
    prefid: int
    protoform: str
    gloss: str
    matches: dict[str, tuple[str, str]]  # lang -> (hypothesis, reference)
    mismatches: list[Mismatch]

    @property
    def error_count(self) -> int:
        return len(self.mismatches)

    @property
    def total_comparisons(self) -> int:
        return len(self.matches) + len(self.mismatches)

    def format_report(self, use_color: bool = True) -> str:
        """Format this result as a human-readable report."""
        lines = [f"Reflexes of /{self.protoform}/ ({self.gloss})"]

        # Show matches
        for lang, (hyp, ref) in sorted(self.matches.items()):
            lines.append(f"  ✅ {lang:8s}  hypothesis: {hyp:10s}  reference: {ref}")

        # Show mismatches
        for mm in self.mismatches:
            lines.append(
                f"  ❌ {mm.language:8s}  hypothesis: {mm.hypothesis:10s}  "
                f"reference: {mm.reference}"
            )
            lines.append(mm.format_diff(use_color))

        return "\n".join(lines)


@dataclass
class EvaluationMetrics:
    """Aggregate metrics from evaluation."""
    total_cognate_sets: int
    total_comparisons: int
    total_errors: int
    num_laws: int
    num_law_references: int
    laws_coeff: float
    refs_coeff: float

    @property
    def accuracy(self) -> float:
        if self.total_comparisons == 0:
            return 0.0
        return (self.total_comparisons - self.total_errors) / self.total_comparisons

    @property
    def penalty(self) -> float:
        return self.laws_coeff * self.num_laws + self.refs_coeff * self.num_law_references

    @property
    def score(self) -> float:
        return self.total_errors + self.penalty

    def format_report(self) -> str:
        """Format metrics as a human-readable summary."""
        lines = [
            f"Errors:   {self.total_errors} across {self.total_cognate_sets} "
            f"cognate set{'s' if self.total_cognate_sets != 1 else ''}",
            f"Accuracy: {self.accuracy:.1%} ({self.total_comparisons - self.total_errors}/"
            f"{self.total_comparisons})",
            f"Penalty:  {self.penalty:.1f}  ({self.laws_coeff} × {self.num_laws} laws"
            f" + {self.refs_coeff} × {self.num_law_references} refs)",
            f"Score:    {self.score:.1f}",
        ]
        return "\n".join(lines)


@dataclass
class EvaluationReport:
    """Complete evaluation report with metrics and per-set results."""
    metrics: EvaluationMetrics
    results: list[CognateSetResult]
    errors_only: bool = False

    def format_report(self, use_color: bool = True, errors_only: bool = False) -> str:
        """Format the complete report as a string.

        Args:
            use_color: Whether to include ANSI color codes.
            errors_only: If True, only show cognate sets with errors.
        """
        lines = []

        for result in self.results:
            if errors_only and result.error_count == 0:
                continue
            lines.append(result.format_report(use_color))
            lines.append("")

        lines.append(self.metrics.format_report())
        return "\n".join(lines)

    def get_error_results(self) -> list[CognateSetResult]:
        """Return only cognate sets with errors."""
        return [r for r in self.results if r.error_count > 0]


class ForwardReconstructionEvaluator:
    """Evaluates a forward reconstruction against database cognate sets."""

    def __init__(
        self,
        reconstruction: ForwardReconstruction,
        db_path: str,
        proto_langid: Optional[int] = None,
        proto_glottocode: Optional[str] = None,
        laws_coeff: float = 0.5,
        refs_coeff: float = 2.5,
    ):
        """Initialize the evaluator.

        Args:
            reconstruction: The forward reconstruction system.
            db_path: Path to the SQLite database.
            proto_langid: Language ID for the proto-language (optional if proto_glottocode provided).
            proto_glottocode: Glottocode for the proto-language (optional if proto_langid provided).
            laws_coeff: Coefficient for number of laws in penalty.
            refs_coeff: Coefficient for law references in penalty.
        """
        self.reconstruction = reconstruction
        self.db_path = db_path
        self._proto_langid = proto_langid
        self._proto_glottocode = proto_glottocode
        self.laws_coeff = laws_coeff
        self.refs_coeff = refs_coeff
        self._lang_id_to_name: dict[int, str] = {}
        self._lang_name_to_id: dict[str, int] = {}
        self._glottocode_to_langid: dict[str, int] = {}
        self._langid_to_glottocode: dict[int, str] = {}

    def _load_language_mappings(self, conn: sqlite3.Connection) -> None:
        """Load language ID, name, and glottocode mappings."""
        cursor = conn.cursor()
        cursor.execute("SELECT langid, name, glottocode FROM langnames")
        for langid, name, glottocode in cursor.fetchall():
            self._lang_id_to_name[langid] = name
            self._lang_name_to_id[name] = langid
            if glottocode and glottocode != 'unk':
                self._glottocode_to_langid[glottocode] = langid
                self._langid_to_glottocode[langid] = glottocode

    def _resolve_proto_langid(self) -> int:
        """Resolve the proto-language ID from langid or glottocode."""
        if self._proto_langid is not None:
            return self._proto_langid
        if self._proto_glottocode is not None:
            langid = self._glottocode_to_langid.get(self._proto_glottocode)
            if langid is None:
                raise ValueError(f"Unknown proto-language glottocode: {self._proto_glottocode}")
            return langid
        raise ValueError("Either proto_langid or proto_glottocode must be provided")

    def _resolve_glottocode_to_langid(self, glottocode: str) -> Optional[int]:
        """Resolve a glottocode to a language ID."""
        return self._glottocode_to_langid.get(glottocode)

    def _get_language_identifier(self, langid: int) -> str:
        """Get the glottocode for a language ID, falling back to name."""
        glottocode = self._langid_to_glottocode.get(langid)
        if glottocode:
            return glottocode
        return self._lang_id_to_name.get(langid, f"lang_{langid}")

    def _get_cognate_sets(self, conn: sqlite3.Connection, proto_langid: int) -> list[dict]:
        """Load cognate sets from the database.

        Returns a list of dicts, each with:
        - prefid: protoform reflex ID
        - protoform: the proto-form string
        - gloss: the gloss
        - reflexes: dict mapping glottocode (or language name) to (refid, form)
        """
        cursor = conn.cursor()

        # Get all protoforms for the specified proto-language
        cursor.execute(
            """
            SELECT refid, ipaform, gloss
            FROM reflexes
            WHERE langid = ? AND ipaform IS NOT NULL AND ipaform != ''
            """,
            (proto_langid,),
        )
        protoforms = cursor.fetchall()

        cognate_sets = []
        for prefid, protoform, gloss in protoforms:
            # Get all reflexes for this protoform
            cursor.execute(
                """
                SELECT r.refid, r.langid, r.ipaform, ro.morph_index
                FROM reflexes r
                JOIN reflex_of ro ON r.refid = ro.refid
                WHERE ro.prefid = ? AND r.ipaform IS NOT NULL AND r.ipaform != ''
                """,
                (prefid,),
            )

            reflexes = {}
            for refid, langid, form, morph_index in cursor.fetchall():
                # Use glottocode as the key, falling back to language name
                lang_identifier = self._get_language_identifier(langid)
                # Extract the relevant morpheme
                morphemes = re.split(r"[-\s]+", form)
                morphemes = [m for m in morphemes if m]
                if morphemes and 0 <= morph_index < len(morphemes):
                    form = morphemes[morph_index]
                reflexes[lang_identifier] = (refid, form)

            if reflexes:  # Only include sets with at least one reflex
                cognate_sets.append({
                    "prefid": prefid,
                    "protoform": protoform,
                    "gloss": gloss or "",
                    "reflexes": reflexes,
                })

        return cognate_sets

    def evaluate(self) -> EvaluationReport:
        """Run evaluation and return the report."""
        conn = sqlite3.connect(self.db_path)
        try:
            self._load_language_mappings(conn)
            proto_langid = self._resolve_proto_langid()
            cognate_sets = self._get_cognate_sets(conn, proto_langid)
        finally:
            conn.close()

        leaf_languages = self.reconstruction.get_leaf_languages()
        results = []
        total_errors = 0
        total_comparisons = 0

        for cog_set in cognate_sets:
            hypotheses = self.reconstruction.apply_laws(cog_set["protoform"])

            matches = {}
            mismatches = []

            # lang_identifier is now a glottocode (or language name as fallback)
            for lang_identifier, (refid, reference) in cog_set["reflexes"].items():
                if lang_identifier not in leaf_languages:
                    continue

                hypothesis = hypotheses.get(lang_identifier, "???")
                total_comparisons += 1

                if hypothesis == reference:
                    matches[lang_identifier] = (hypothesis, reference)
                else:
                    mismatches.append(Mismatch(
                        language=lang_identifier,
                        hypothesis=hypothesis,
                        reference=reference,
                    ))
                    total_errors += 1

            results.append(CognateSetResult(
                prefid=cog_set["prefid"],
                protoform=cog_set["protoform"],
                gloss=cog_set["gloss"],
                matches=matches,
                mismatches=mismatches,
            ))

        metrics = EvaluationMetrics(
            total_cognate_sets=len(cognate_sets),
            total_comparisons=total_comparisons,
            total_errors=total_errors,
            num_laws=len(self.reconstruction.laws),
            num_law_references=self.reconstruction.count_law_references(),
            laws_coeff=self.laws_coeff,
            refs_coeff=self.refs_coeff,
        )

        return EvaluationReport(metrics=metrics, results=results)


def evaluate_from_yaml(
    yaml_str: str,
    db_path: str,
    proto_langid: Optional[int] = None,
    proto_glottocode: Optional[str] = None,
    laws_coeff: float = 0.5,
    refs_coeff: float = 2.5,
) -> EvaluationReport:
    """Convenience function to evaluate a YAML reconstruction against a database.

    Args:
        yaml_str: YAML string defining the forward reconstruction.
        db_path: Path to the SQLite database.
        proto_langid: Language ID for the proto-language (optional if proto_glottocode provided).
        proto_glottocode: Glottocode for the proto-language (optional if proto_langid provided).
        laws_coeff: Coefficient for number of laws in penalty.
        refs_coeff: Coefficient for law references in penalty.

    Returns:
        EvaluationReport with metrics and per-cognate-set results.
    """
    reconstruction = ForwardReconstruction.from_yaml(yaml_str)
    evaluator = ForwardReconstructionEvaluator(
        reconstruction=reconstruction,
        db_path=db_path,
        proto_langid=proto_langid,
        proto_glottocode=proto_glottocode,
        laws_coeff=laws_coeff,
        refs_coeff=refs_coeff,
    )
    return evaluator.evaluate()


def load_yaml_file(path: str) -> str:
    """Load a YAML file and return its contents as a string."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def evaluate_from_file(
    yaml_path: str,
    db_path: Optional[str] = None,
    proto_langid: Optional[int] = None,
    proto_glottocode: Optional[str] = None,
    laws_coeff: float = 0.5,
    refs_coeff: float = 2.5,
) -> EvaluationReport:
    """Evaluate a forward reconstruction YAML file against a database.

    Args:
        yaml_path: Path to the YAML file defining the forward reconstruction.
        db_path: Path to the SQLite database (defaults to db/borderlands.sqlite3).
        proto_langid: Language ID for the proto-language (optional if proto_glottocode provided).
        proto_glottocode: Glottocode for the proto-language (optional if proto_langid provided).
        laws_coeff: Coefficient for number of laws in penalty.
        refs_coeff: Coefficient for law references in penalty.

    Returns:
        EvaluationReport with metrics and per-cognate-set results.
    """
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)

    yaml_str = load_yaml_file(yaml_path)
    return evaluate_from_yaml(
        yaml_str=yaml_str,
        db_path=db_path,
        proto_langid=proto_langid,
        proto_glottocode=proto_glottocode,
        laws_coeff=laws_coeff,
        refs_coeff=refs_coeff,
    )


def list_reconstruction_files(directory: Optional[str] = None) -> list[str]:
    """List all YAML reconstruction files in the specified directory.

    Args:
        directory: Path to directory (defaults to forward_reconstruction/).

    Returns:
        List of YAML file paths.
    """
    if directory is None:
        directory = str(DEFAULT_RECONSTRUCTION_DIR)

    pattern = os.path.join(directory, "*.yaml")
    return sorted(glob.glob(pattern))


def get_reconstruction_by_name(name: str, directory: Optional[str] = None) -> Optional[str]:
    """Find a reconstruction file by its 'name' field.

    Args:
        name: The name field value to search for.
        directory: Path to directory (defaults to forward_reconstruction/).

    Returns:
        Path to the matching YAML file, or None if not found.
    """
    for filepath in list_reconstruction_files(directory):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data.get("name") == name:
                    return filepath
        except (yaml.YAMLError, IOError):
            continue
    return None


def main():
    """Command-line interface for forward reconstruction evaluation."""
    parser = argparse.ArgumentParser(
        description="Evaluate forward reconstruction sound laws against cognate data."
    )
    parser.add_argument(
        "yaml_file",
        nargs="?",
        help="Path to YAML file, or name of reconstruction in forward_reconstruction/",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--proto-langid",
        type=int,
        help="Language ID for the proto-language",
    )
    parser.add_argument(
        "--proto-glottocode",
        help="Glottocode for the proto-language",
    )
    parser.add_argument(
        "--laws-coeff",
        type=float,
        default=0.5,
        help="Coefficient for number of laws in penalty (default: 0.5)",
    )
    parser.add_argument(
        "--refs-coeff",
        type=float,
        default=2.5,
        help="Coefficient for law references in penalty (default: 2.5)",
    )
    parser.add_argument(
        "--errors-only",
        action="store_true",
        help="Only show cognate sets with errors",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available reconstruction files",
    )

    args = parser.parse_args()

    if args.list:
        files = list_reconstruction_files()
        if not files:
            print(f"No YAML files found in {DEFAULT_RECONSTRUCTION_DIR}")
            return

        print("Available reconstruction files:")
        for filepath in files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    name = data.get("name", "unnamed")
                print(f"  {name}: {filepath}")
            except (yaml.YAMLError, IOError) as e:
                print(f"  (error reading {filepath}: {e})")
        return

    if not args.yaml_file:
        parser.error("yaml_file is required unless --list is specified")

    # Resolve yaml_file: could be a path or a name
    if os.path.exists(args.yaml_file):
        yaml_path = args.yaml_file
    else:
        # Try to find by name
        yaml_path = get_reconstruction_by_name(args.yaml_file)
        if yaml_path is None:
            # Try as a filename in the default directory
            potential_path = DEFAULT_RECONSTRUCTION_DIR / f"{args.yaml_file}.yaml"
            if potential_path.exists():
                yaml_path = str(potential_path)
            else:
                parser.error(
                    f"Could not find reconstruction file: {args.yaml_file}\n"
                    f"Use --list to see available reconstructions."
                )

    report = evaluate_from_file(
        yaml_path=yaml_path,
        db_path=args.db,
        proto_langid=args.proto_langid,
        proto_glottocode=args.proto_glottocode,
        laws_coeff=args.laws_coeff,
        refs_coeff=args.refs_coeff,
    )

    print(report.format_report(use_color=not args.no_color, errors_only=args.errors_only))


if __name__ == "__main__":
    main()
