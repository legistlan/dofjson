import re
import subprocess
import unittest
from pathlib import Path

from dofjson import cli

ROOT = Path(__file__).resolve().parents[1]

_AUTOMODULE_RE = re.compile(r"^\.\.\s+automodule::\s+(\S+)\s*$", re.MULTILINE)


class TestEveryModuleHasExactlyOneAutomodulePage(unittest.TestCase):
    def test_every_module_is_documented_exactly_once(self):
        module_names = sorted(
            f"dofjson.{path.stem}"
            for path in (ROOT / "dofjson").glob("*.py")
            if path.stem != "__init__"
        )
        self.assertTrue(module_names, "expected at least one dofjson/*.py module")

        rst_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "docs" / "source").rglob("*.rst")
        )
        documented = _AUTOMODULE_RE.findall(rst_text)

        for name in module_names:
            occurrences = documented.count(name)
            self.assertEqual(
                occurrences, 1,
                f"{name} is named by {occurrences} automodule directives under "
                "docs/source/, expected exactly 1",
            )


class TestCliPageNamesEveryOption(unittest.TestCase):
    def test_every_option_string_appears_in_the_cli_page(self):
        page = (ROOT / "website" / "pages" / "cli.qmd").read_text(encoding="utf-8")
        options = sorted(
            option
            for action in cli.build_parser()._actions
            for option in action.option_strings
            if option not in ("-h", "--help")
        )
        self.assertIn("--cache-dir", options)

        missing = [option for option in options if option not in page]
        self.assertFalse(
            missing,
            "website/pages/cli.qmd does not name these options: " + ", ".join(missing),
        )


class TestNoDeadDocumentationUrls(unittest.TestCase):
    """Documentation links of this package point at legistlan, not at pages that are gone.

    The Read the Docs site of the LegalIA monorepo answers 404 and document2md
    moved from the INGEOTEC organization to ``legistlan/document2md``; the pages
    live on GitHub Pages (``legistlan.github.io``). Links to the ``INGEOTEC/LegalIA`` monorepo and its
    ``notas-archivo`` release are not listed: both are still there.
    """

    # Built from fragments so this file does not flag itself.
    DEAD = (
        "legalia." + "readthedocs.io",
        "readthedocs.org/projects/" + "legalia",
        "github.com/INGEOTEC/" + "document2md",
        "ingeotec." + "github.io",
    )

    def test_no_tracked_file_mentions_a_dead_url(self):
        try:
            listing = subprocess.run(
                ["git", "ls-files", "-z"],
                cwd=ROOT, capture_output=True, check=True,
            ).stdout
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git is not available or ROOT is not a git checkout")

        offenders = {}
        for name in filter(None, listing.decode("utf-8").split("\0")):
            path = ROOT / name
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            found = [url for url in self.DEAD if url in text]
            if found:
                offenders[name] = found

        self.assertFalse(
            offenders,
            "tracked files point at dead documentation URLs: "
            + "; ".join(f"{n}: {', '.join(u)}" for n, u in sorted(offenders.items())),
        )


if __name__ == "__main__":
    unittest.main()
