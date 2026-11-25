#!/usr/bin/env python3
"""
Arma el sitio del flasher en _site/: copia site/, y para cada dispositivo de devices.json baja los
.bin del último release de su repo y escribe los manifiestos de ESP Web Tools.

Los .bin tienen que estar en el mismo sitio: GitHub sirve los archivos de los releases sin los
encabezados CORS que pide el navegador, así que la página no los puede bajar de ahí directo.

Por dispositivo, en _site/firmware/<id>/:
  update.json   Actualizar: solo la app (en app_offset) y el selector de arranque (otadata) como en
                la imagen de fábrica, para que arranque la app nueva aunque antes se haya actualizado por OTA.
                No borra nada más: la configuración del nodo (LittleFS) queda.
  install.json  Instalación limpia: borra toda la flash y graba el .factory.bin en 0.
  index.json    (uno solo, en _site/firmware/) lo que muestra la página.

Uso: GITHUB_TOKEN=... python3 scripts/build_site.py   (el token es opcional: solo sube el límite de la API)
"""
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "_site")
API = "https://api.github.com"


def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": "calandria-flasher", "Accept": "application/vnd.github+json"})
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith(API):
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    return data if binary else json.loads(data)


def short_version(tag):
    """calandria-0.6.0 -> 0.6.0; los viejos v2.8.3-ws154.5 -> ws154.5."""
    if tag.startswith("calandria-"):
        return tag[len("calandria-"):]
    return tag.rsplit("-", 1)[-1]


def meshtastic_version(release, names):
    m = re.search(r"Meshtastic (\d+\.\d+\.\d+)", release.get("name") or "")
    if m:
        return m.group(1)
    m = re.match(r"v(\d+\.\d+\.\d+)-", release["tag_name"])
    if m:
        return m.group(1)
    for n in names:
        m = re.search(r"-(\d+\.\d+\.\d+)\.[0-9a-f]{7}", n)
        if m:
            return m.group(1)
    return None


def latest_release(repo):
    """
    El que GitHub marca como "Latest" (el mismo que usa CalandriApp). Si no hay ninguno (solo
    pre-releases), el publicado más nuevo por fecha: la lista de /releases no viene ordenada por fecha.
    """
    try:
        return get(f"{API}/repos/{repo}/releases/latest")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    rels = [r for r in get(f"{API}/repos/{repo}/releases?per_page=50") if not r.get("draft") and r.get("published_at")]
    return max(rels, key=lambda r: r["published_at"]) if rels else None


def build_device(dev):
    rel = latest_release(dev["repo"])
    if rel is None:
        print(f"{dev['id']}: sin releases", file=sys.stderr)
        return None
    assets = [a for a in rel["assets"]
              if a["name"].startswith(dev["asset_prefix"]) and a["name"].endswith(".bin")
              and not any(x in a["name"] for x in dev.get("exclude", []))]
    factory = next((a for a in assets if a["name"].endswith(".factory.bin")), None)
    app = next((a for a in assets if not a["name"].endswith(".factory.bin")), None)
    if factory is None or app is None:
        print(f"{dev['id']}: el release {rel['tag_name']} no tiene .bin y .factory.bin", file=sys.stderr)
        return None

    out = os.path.join(OUT, "firmware", dev["id"])
    os.makedirs(out, exist_ok=True)
    blobs = {}
    for a in (factory, app):
        # browser_download_url: público, sin token (el token no tiene que viajar al redirect de descarga)
        data = get(a["browser_download_url"], binary=True)
        if len(data) != a["size"]:
            raise RuntimeError(f"{a['name']}: bajé {len(data)} bytes, esperaba {a['size']}")
        with open(os.path.join(out, a["name"]), "wb") as f:
            f.write(data)
        blobs[a["name"]] = data
    # Chequeo: la app del .factory.bin (en app_offset) tiene que ser la misma que el .bin.
    fac, ap = blobs[factory["name"]], blobs[app["name"]]
    off = dev["app_offset"]
    if fac[off:off + len(ap)] != ap:
        raise RuntimeError(f"{dev['id']}: el .bin no coincide con la app del .factory.bin")
    # Selector de arranque (otadata) igual al de la imagen de fábrica: arranca app0, la que grabamos,
    # aunque antes el nodo se haya actualizado por OTA desde la otra ranura.
    o, n = dev["otadata_offset"], dev["otadata_size"]
    otadata = fac[o:o + n] if len(fac) >= o + n else b"\xff" * n
    with open(os.path.join(out, "otadata.bin"), "wb") as f:
        f.write(otadata)

    version = short_version(rel["tag_name"])
    name = dev["name"]
    update = {
        "name": name,
        "version": version,
        # Sin esto ESP Web Tools borra toda la flash al instalar. Con esto pregunta, con la casilla
        # "Erase device" sin marcar: Actualizar la deja así.
        "new_install_prompt_erase": True,
        "builds": [{
            "chipFamily": dev["chip"],
            "parts": [
                {"path": "otadata.bin", "offset": dev["otadata_offset"]},
                {"path": app["name"], "offset": dev["app_offset"]},
            ],
        }],
    }
    install = {
        "name": name,
        "version": version,
        "new_install_prompt_erase": False,  # siempre borra todo antes de grabar
        "builds": [{"chipFamily": dev["chip"], "parts": [{"path": factory["name"], "offset": 0}]}],
    }
    for fn, m in (("update.json", update), ("install.json", install)):
        with open(os.path.join(out, fn), "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=2)

    print(f"{dev['id']}: {rel['tag_name']} ({app['name']}, {factory['name']})")
    return {
        "id": dev["id"],
        "name": name,
        "description": dev.get("description", ""),
        "chip": dev["chip"],
        "version": version,
        "tag": rel["tag_name"],
        "meshtastic": meshtastic_version(rel, [app["name"], factory["name"]]),
        "published": rel.get("published_at"),
        "prerelease": rel.get("prerelease", False),
        "notes_url": rel["html_url"],
        "docs": dev.get("docs"),
        "update": f"firmware/{dev['id']}/update.json",
        "install": f"firmware/{dev['id']}/install.json",
    }


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(os.path.join(ROOT, "site"), OUT)
    with open(os.path.join(ROOT, "devices.json"), encoding="utf-8") as f:
        devices = json.load(f)
    index = [d for d in (build_device(dev) for dev in devices) if d]
    if not index:
        sys.exit("ningún dispositivo tiene firmware publicado")
    os.makedirs(os.path.join(OUT, "firmware"), exist_ok=True)
    with open(os.path.join(OUT, "firmware", "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    # GitHub Pages no tiene que pasar el sitio por Jekyll.
    open(os.path.join(OUT, ".nojekyll"), "w").close()


if __name__ == "__main__":
    main()
