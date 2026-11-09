import contextlib
import importlib.util
import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "copiar_notas_archivo", ROOT / "scripts" / "copiar_notas_archivo.py"
)
copiar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(copiar)


def _done(stdout="", returncode=0):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


def _not_found():
    return subprocess.CalledProcessError(
        1, ["gh"], output="", stderr="gh: Not Found (HTTP 404)"
    )


class TestDiferencias(unittest.TestCase):
    def test_identical_listings_have_no_differences(self):
        listing = {"notas-2025.tgz": 10, "notas-2026-01.tgz": 5}
        self.assertEqual(copiar.diferencias(listing, dict(listing)), ([], []))

    def test_missing_names_are_reported_sorted(self):
        origen = {"b.tgz": 1, "a.tgz": 2, "c.tgz": 3}
        self.assertEqual(copiar.diferencias(origen, {"c.tgz": 3}), (["a.tgz", "b.tgz"], []))

    def test_size_mismatch_is_reported(self):
        origen = {"a.tgz": 2, "b.tgz": 3}
        self.assertEqual(copiar.diferencias(origen, {"a.tgz": 2, "b.tgz": 4}), ([], ["b.tgz"]))

    def test_an_asset_only_in_the_destination_is_not_a_difference(self):
        self.assertEqual(copiar.diferencias({"a.tgz": 1}, {"a.tgz": 1, "z.tgz": 9}), ([], []))

    def test_empty_destination_misses_everything(self):
        self.assertEqual(copiar.diferencias({"a.tgz": 1}, {}), (["a.tgz"], []))


class TestListar(unittest.TestCase):
    def test_parses_the_tsv_into_name_and_size(self):
        tsv = "notas-1917.tgz\t100\nnotas-2026-10.tgz\t2048\n\n"
        with mock.patch.object(subprocess, "run", return_value=_done(tsv)) as run:
            self.assertEqual(
                copiar.listar("example/repo"),
                {"notas-1917.tgz": 100, "notas-2026-10.tgz": 2048},
            )
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[:3], ["gh", "api", "repos/example/repo/releases/tags/notas-archivo"])
        self.assertTrue(run.call_args.kwargs["check"])
        self.assertNotIn("shell", run.call_args.kwargs)

    def test_a_missing_release_is_an_empty_dict(self):
        with mock.patch.object(subprocess, "run", side_effect=_not_found()):
            self.assertEqual(copiar.listar("example/repo"), {})

    def test_any_other_failure_is_raised(self):
        boom = subprocess.CalledProcessError(1, ["gh"], output="", stderr="HTTP 500")
        with mock.patch.object(subprocess, "run", side_effect=boom):
            with self.assertRaises(subprocess.CalledProcessError):
                copiar.listar("example/repo")


class TestMain(unittest.TestCase):
    def _run(self, argv, run):
        out = io.StringIO()
        with mock.patch.object(subprocess, "run", side_effect=run), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = copiar.main(argv)
        return code, out.getvalue()

    def test_source_is_required(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as ctx:
            copiar.main([])
        self.assertEqual(ctx.exception.code, 2)

    def test_dry_run_runs_no_create_download_or_upload(self):
        calls = []

        def run(cmd, **kwargs):
            calls.append(cmd)
            if cmd[:2] == ["gh", "api"]:
                if "repos/example/src/" in cmd[2]:
                    return _done("notas-2025.tgz\t10\n")
                raise _not_found()
            if cmd[:3] == ["gh", "release", "view"]:
                raise subprocess.CalledProcessError(1, cmd, output="", stderr="release not found")
            raise AssertionError(f"dry-run ran {cmd}")

        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp) / "copia"
            code, out = self._run(["example/src", "--dry-run", "--outdir", str(outdir)], run)
            self.assertFalse(outdir.exists())
        self.assertEqual(code, 0)
        self.assertIn("[dry-run]", out)
        self.assertFalse(any(c[:3] in (["gh", "release", "create"],
                                       ["gh", "release", "upload"]) for c in calls))

    def test_copy_creates_the_release_uploads_and_verifies(self):
        sizes = {"notas-2025.tgz": 4, "notas-2026-01.tgz": 3}
        calls = []
        state = {"uploaded": False, "created": False}

        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp) / "copia"

            def run(cmd, **kwargs):
                calls.append(cmd)
                if cmd[:2] == ["gh", "api"]:
                    if "example/src" in cmd[2]:
                        return _done("".join(f"{n}\t{s}\n" for n, s in sizes.items()))
                    if not state["uploaded"]:
                        raise _not_found()
                    return _done("".join(f"{n}\t{s}\n" for n, s in sizes.items()))
                if cmd[:3] == ["gh", "release", "download"]:
                    outdir.mkdir(parents=True, exist_ok=True)
                    for n, s in sizes.items():
                        (outdir / n).write_bytes(b"x" * s)
                    return _done()
                if cmd[:3] == ["gh", "release", "view"]:
                    raise subprocess.CalledProcessError(1, cmd, output="", stderr="not found")
                if cmd[:3] == ["gh", "release", "create"]:
                    state["created"] = True
                    return _done()
                if cmd[:3] == ["gh", "release", "upload"]:
                    state["uploaded"] = True
                    return _done()
                raise AssertionError(cmd)

            code, out = self._run(["example/src", "--outdir", str(outdir)], run)

        self.assertEqual(code, 0)
        self.assertTrue(state["created"])
        upload = next(c for c in calls if c[:3] == ["gh", "release", "upload"])
        self.assertIn("legistlan/dofjson", upload)
        self.assertIn("--clobber", upload)
        self.assertEqual(sum(1 for a in upload if a.endswith(".tgz")), 2)
        self.assertIn("2 assets en el origen, 2 en el destino", out)

    def test_exits_non_zero_when_the_destination_still_differs(self):
        sizes = {"notas-2025.tgz": 4}
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp) / "copia"

            def run(cmd, **kwargs):
                if cmd[:2] == ["gh", "api"]:
                    if "example/src" in cmd[2]:
                        return _done("notas-2025.tgz\t4\n")
                    return _done("notas-2025.tgz\t1\n")   # truncated upload
                if cmd[:3] == ["gh", "release", "download"]:
                    outdir.mkdir(parents=True, exist_ok=True)
                    (outdir / "notas-2025.tgz").write_bytes(b"x" * 4)
                return _done()

            code, _ = self._run(["example/src", "--outdir", str(outdir)], run)
        self.assertEqual(code, 1)

    def test_a_download_of_the_wrong_size_stops_the_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp) / "copia"
            calls = []

            def run(cmd, **kwargs):
                calls.append(cmd)
                if cmd[:2] == ["gh", "api"]:
                    if "example/src" in cmd[2]:
                        return _done("notas-2025.tgz\t4\n")
                    raise _not_found()
                if cmd[:3] == ["gh", "release", "download"]:
                    outdir.mkdir(parents=True, exist_ok=True)
                    (outdir / "notas-2025.tgz").write_bytes(b"xx")
                return _done()

            with self.assertRaises(SystemExit):
                self._run(["example/src", "--outdir", str(outdir)], run)
        self.assertFalse(any(c[:3] == ["gh", "release", "upload"] for c in calls))


class TestWorkflowSchedule(unittest.TestCase):
    def test_monthly_schedule_is_on(self):
        lines = (ROOT / ".github" / "workflows" / "notas-archivo.yml").read_text(
            encoding="utf-8").splitlines()
        self.assertIn("  schedule:", lines)
        self.assertIn('    - cron: "0 9 1 * *"', lines)


if __name__ == "__main__":
    unittest.main()
