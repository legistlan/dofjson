#!/usr/bin/env python3
"""Copy the `notas-archivo` release of one repository into another, once.

The release holds one `notas-YYYY.tgz` per closed year and one
`notas-YYYY-MM.tgz` per month of the current year. Rebuilding it from SIDOF
means about 40,000 days at a 0.5 s pause (more than a six-hour Actions job)
and would lose the days already repaired from www.dof.gob.mx, so a move to
another owner copies the assets byte for byte instead.

The source repository is required and has no default; the destination is this
repository. Run with --dry-run first: it lists both releases, the differences
and the `gh` commands it would run, and writes nothing to GitHub (nor to disk).

    ./scripts/copiar_notas_archivo.py <owner>/<name> --dry-run
    ./scripts/copiar_notas_archivo.py <owner>/<name>

Only `gh`, already authenticated with write access to the destination, is
needed; the downloads land in --outdir (do not commit them). The script ends
by listing the destination again and exits non-zero if any asset is missing
or differs in size from the source.
"""

import argparse
import subprocess
import sys
from pathlib import Path

TAG = "notas-archivo"
DESTINO_PREDETERMINADO = "legistlan/dofjson"
TITULO = "Archivo de notas del DOF"
# The same notes `.github/workflows/notas-archivo.yml` gives a release it creates.
NOTAS = "Índices diarios de notas del DOF generados por el workflow notas-archivo.yml."


def gh(*args: str) -> subprocess.CompletedProcess:
    """Run `gh` with `args`; raise CalledProcessError on a non-zero exit.

    A list, never a shell: repository names and paths are not interpreted.
    """
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True)


def listar(repo: str) -> dict[str, int]:
    """Map every asset of `repo`'s release to its size in bytes.

    A release that does not exist is an empty dict, not an error: `gh api`
    exits 1 with a 404 in stderr, which is the normal state of a destination
    that has not been copied to yet. Any other failure is raised.
    """
    try:
        salida = gh("api", f"repos/{repo}/releases/tags/{TAG}",
                    "--jq", r".assets[] | [.name, .size] | @tsv").stdout
    except subprocess.CalledProcessError as exc:
        error = (exc.stderr or "") + (exc.stdout or "")
        if "404" in error or "Not Found" in error:
            return {}
        raise
    assets = {}
    for linea in salida.splitlines():
        if not linea.strip():
            continue
        nombre, tamano = linea.split("\t")
        assets[nombre] = int(tamano)
    return assets


def diferencias(origen: dict[str, int], destino: dict[str, int]) -> tuple[list[str], list[str]]:
    """Names missing from `destino`, and names whose size differs, sorted.

    An asset only in `destino` is not a difference: the copy never deletes.
    """
    faltan = sorted(n for n in origen if n not in destino)
    distintos = sorted(n for n in origen if n in destino and origen[n] != destino[n])
    return faltan, distintos


def descarga(origen: str, outdir: Path, esperado: dict[str, int]) -> list[Path]:
    """Download every `.tgz` of `origen`'s release and check each size."""
    outdir.mkdir(parents=True, exist_ok=True)
    gh("release", "download", TAG, "-R", origen, "-p", "*.tgz", "-D", str(outdir),
       "--clobber")
    archivos = []
    for nombre, tamano in sorted(esperado.items()):
        ruta = outdir / nombre
        if not ruta.is_file():
            raise SystemExit(f"{nombre}: no se descargó")
        if ruta.stat().st_size != tamano:
            raise SystemExit(f"{nombre}: descargó {ruta.stat().st_size} bytes, "
                             f"el listado dice {tamano}")
        archivos.append(ruta)
    return archivos


def existe_release(repo: str) -> bool:
    try:
        gh("release", "view", TAG, "-R", repo)
    except subprocess.CalledProcessError:
        return False
    return True


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("origen", help="<owner>/<name> whose notas-archivo release is copied")
    p.add_argument("--destino", default=DESTINO_PREDETERMINADO,
                   help="<owner>/<name> that receives it (default: %(default)s)")
    p.add_argument("--outdir", default="notas-archivo-copia",
                   help="where the downloaded .tgz land (default: %(default)s)")
    p.add_argument("--dry-run", action="store_true",
                   help="print the listings, the differences and the commands; write nothing")
    args = p.parse_args(argv)

    origen = listar(args.origen)
    if not origen:
        sys.exit(f"{args.origen} no tiene el release {TAG} (o no tiene assets)")
    destino = listar(args.destino)
    faltan, distintos = diferencias(origen, destino)
    outdir = Path(args.outdir)
    print(f"origen  {args.origen}: {len(origen)} assets, "
          f"{sum(origen.values())} bytes", flush=True)
    print(f"destino {args.destino}: {len(destino)} assets, "
          f"{sum(destino.values())} bytes", flush=True)
    print(f"faltan {len(faltan)}, con tamaño distinto {len(distintos)}", flush=True)

    crear = ["gh", "release", "create", TAG, "-R", args.destino,
             "--title", TITULO, "--notes", NOTAS]
    subir = ["gh", "release", "upload", TAG, f"{outdir}/*.tgz",
             "-R", args.destino, "--clobber"]
    if args.dry_run:
        print("\n[dry-run] descargaría "
              f"gh release download {TAG} -R {args.origen} -p '*.tgz' -D {outdir}")
        if not destino and not existe_release(args.destino):
            print("[dry-run] crearía el release:", " ".join(crear))
        print("[dry-run] subiría:", " ".join(subir))
        return 0

    archivos = descarga(args.origen, outdir, origen)
    print(f"descargados {len(archivos)} archivos en {outdir}", flush=True)
    if not existe_release(args.destino):
        gh(*crear[1:])
        print(f"creado el release {TAG} en {args.destino}", flush=True)
    gh("release", "upload", TAG, *map(str, archivos), "-R", args.destino, "--clobber")

    final = listar(args.destino)
    faltan, distintos = diferencias(origen, final)
    print(f"\n{len(origen)} assets en el origen, {len(final)} en el destino", flush=True)
    if faltan or distintos:
        print(f"faltan: {faltan}", file=sys.stderr)
        print(f"con tamaño distinto: {distintos}", file=sys.stderr)
        return 1
    print("el destino tiene todos los assets, con el mismo tamaño", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
