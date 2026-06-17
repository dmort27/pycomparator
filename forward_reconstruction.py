"""
Forward reconstruction evaluation module.

Evaluates sound law systems defined in YAML format against cognate data
from a SQLite database. Provides metrics and error reports via an API.
"""

import difflib
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Callable, Optional

import yaml


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
    laws: dict[str, SoundLaw]
    tree: dict[str, list[TreeNode]]

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "ForwardReconstruction":
        """Parse a forward reconstruction from YAML string."""
        data = yaml.safe_load(yaml_str)

        laws = {}
        for law_id, law_data in data.get("laws", {}).items():
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

        return cls(laws=laws, tree=tree)

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
        proto_langid: int,
        laws_coeff: float = 0.5,
        refs_coeff: float = 2.5,
    ):
        """Initialize the evaluator.

        Args:
            reconstruction: The forward reconstruction system.
            db_path: Path to the SQLite database.
            proto_langid: Language ID for the proto-language.
            laws_coeff: Coefficient for number of laws in penalty.
            refs_coeff: Coefficient for law references in penalty.
        """
        self.reconstruction = reconstruction
        self.db_path = db_path
        self.proto_langid = proto_langid
        self.laws_coeff = laws_coeff
        self.refs_coeff = refs_coeff
        self._lang_id_to_name: dict[int, str] = {}
        self._lang_name_to_id: dict[str, int] = {}

    def _load_language_names(self, conn: sqlite3.Connection) -> None:
        """Load language ID to name mappings."""
        cursor = conn.cursor()
        cursor.execute("SELECT langid, name FROM langnames")
        for langid, name in cursor.fetchall():
            self._lang_id_to_name[langid] = name
            self._lang_name_to_id[name] = langid

    def _get_cognate_sets(self, conn: sqlite3.Connection) -> list[dict]:
        """Load cognate sets from the database.

        Returns a list of dicts, each with:
        - prefid: protoform reflex ID
        - protoform: the proto-form string
        - gloss: the gloss
        - reflexes: dict mapping language name to (refid, form)
        """
        cursor = conn.cursor()

        # Get all protoforms for the specified proto-language
        cursor.execute(
            """
            SELECT refid, ipaform, gloss
            FROM reflexes
            WHERE langid = ? AND ipaform IS NOT NULL AND ipaform != ''
            """,
            (self.proto_langid,),
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
                lang_name = self._lang_id_to_name.get(langid, f"lang_{langid}")
                # Extract the relevant morpheme
                morphemes = re.split(r"[-\s]+", form)
                morphemes = [m for m in morphemes if m]
                if morphemes and 0 <= morph_index < len(morphemes):
                    form = morphemes[morph_index]
                reflexes[lang_name] = (refid, form)

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
            self._load_language_names(conn)
            cognate_sets = self._get_cognate_sets(conn)
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

            for lang_name, (refid, reference) in cog_set["reflexes"].items():
                if lang_name not in leaf_languages:
                    continue

                hypothesis = hypotheses.get(lang_name, "???")
                total_comparisons += 1

                if hypothesis == reference:
                    matches[lang_name] = (hypothesis, reference)
                else:
                    mismatches.append(Mismatch(
                        language=lang_name,
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
    proto_langid: int,
    laws_coeff: float = 0.5,
    refs_coeff: float = 2.5,
) -> EvaluationReport:
    """Convenience function to evaluate a YAML reconstruction against a database.

    Args:
        yaml_str: YAML string defining the forward reconstruction.
        db_path: Path to the SQLite database.
        proto_langid: Language ID for the proto-language.
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
        laws_coeff=laws_coeff,
        refs_coeff=refs_coeff,
    )
    return evaluator.evaluate()


def load_yaml_file(path: str) -> str:
    """Load a YAML file and return its contents as a string."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
