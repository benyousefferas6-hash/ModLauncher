"""Core logic: config, Microsoft auth, game install/launch, Modrinth API, Discord presence."""
import json, os, re, shlex, shutil, subprocess, sys, time, uuid
from pathlib import Path

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

import requests
import minecraft_launcher_lib as mll

_base = Path(os.environ.get("APPDATA", Path.home())) if os.name == "nt" else Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
DATA = _base / "modlauncher"
ASSETS = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "assets"
MC, INST, CFG = DATA / "minecraft", DATA / "instances", DATA / "config.json"
MC.mkdir(parents=True, exist_ok=True)
INST.mkdir(parents=True, exist_ok=True)

APP_VERSION = "v1.0.0"  # release builds get this stamped automatically from the git tag
REPO = "benyousefferas6-hash/ModLauncher"
REDIRECT = "https://login.microsoftonline.com/common/oauth2/nativeclient"
API = "https://api.modrinth.com/v2"
UA = {"User-Agent": "modlauncher/1.0 (personal launcher)"}
DEFAULT_CLIENT_ID = "e79ab79a-3cd2-4911-9ba8-3d0b2cf838d7"
DEFAULTS = {"username": "Player", "ms_client_id": DEFAULT_CLIENT_ID, "discord_app_id": "",
            "ram_mb": 4096, "java_path": "", "account": None, "mode": None, "bg": "auto", "bg_interval": 20, "bg_dim": 40}


# ---------- config ----------
def load_cfg():
    c = dict(DEFAULTS)
    if CFG.exists():
        c.update(json.loads(CFG.read_text()))
    c["ms_client_id"] = c["ms_client_id"] or DEFAULT_CLIENT_ID
    return c


def save_cfg(c):
    CFG.write_text(json.dumps(c, indent=2))


# ---------- Microsoft account ----------
MS = "https://login.microsoftonline.com/consumers/oauth2/v2.0"
SCOPE = "XboxLive.signin offline_access"


def device_start(cfg):
    """Step 1 of device-code login: returns the code the user types at microsoft.com/link."""
    j = requests.post(f"{MS}/devicecode", data={"client_id": cfg["ms_client_id"], "scope": SCOPE}, timeout=20).json()
    if "device_code" not in j:
        raise RuntimeError(j.get("error_description") or str(j))
    return j


def device_poll(cfg, dc, flag):
    """Step 2: wait until the user finishes in the browser. Returns the account, or None if cancelled."""
    end = time.time() + dc.get("expires_in", 900)
    wait = 0
    while time.time() < end:
        if flag["stop"]:
            return None
        time.sleep(1)
        wait += 1
        if wait < dc.get("interval", 5):
            continue
        wait = 0
        r = requests.post(f"{MS}/token", timeout=20, data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": cfg["ms_client_id"], "device_code": dc["device_code"]}).json()
        if "access_token" in r:
            return _minecraft_login(r["access_token"], r["refresh_token"])
        if r.get("error") not in ("authorization_pending", "slow_down"):
            raise RuntimeError(r.get("error_description") or r.get("error"))
    raise RuntimeError("The login code expired. Press Sign in again.")


def ms_refresh(cfg):
    old = cfg["account"]["refresh_token"]
    r = requests.post(f"{MS}/token", timeout=20, data={
        "grant_type": "refresh_token", "client_id": cfg["ms_client_id"], "refresh_token": old, "scope": SCOPE}).json()
    if "access_token" not in r:
        raise RuntimeError("Your Microsoft session expired. Sign in again.")
    return _minecraft_login(r["access_token"], r.get("refresh_token", old))


def _minecraft_login(ms_token, refresh_token):
    """Microsoft token -> Xbox Live -> XSTS -> Minecraft token + profile."""
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    x = requests.post("https://user.auth.xboxlive.com/user/authenticate", headers=h, timeout=20, json={
        "Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com", "RpsTicket": "d=" + ms_token},
        "RelyingParty": "http://auth.xboxlive.com", "TokenType": "JWT"})
    x.raise_for_status()
    s = requests.post("https://xsts.auth.xboxlive.com/xsts/authorize", headers=h, timeout=20, json={
        "Properties": {"SandboxId": "RETAIL", "UserTokens": [x.json()["Token"]]},
        "RelyingParty": "rp://api.minecraftservices.com/", "TokenType": "JWT"})
    if s.status_code == 401:
        err = s.json().get("XErr")
        raise RuntimeError({2148916233: "This Microsoft account has no Xbox profile yet. Log in once at xbox.com to create it.",
                            2148916238: "This is a child account. Add it to a Microsoft family group and allow online play."}
                           .get(err, f"Xbox sign-in was refused (code {err})."))
    s.raise_for_status()
    s = s.json()
    m = requests.post("https://api.minecraftservices.com/authentication/login_with_xbox", timeout=20, json={
        "identityToken": f"XBL3.0 x={s['DisplayClaims']['xui'][0]['uhs']};{s['Token']}"})
    if m.status_code in (401, 403):
        raise RuntimeError("Minecraft refused the sign-in: this launcher hasn't been approved by Mojang yet. Please try again later.")
    m.raise_for_status()
    token = m.json()["access_token"]
    p = requests.get("https://api.minecraftservices.com/minecraft/profile", headers={"Authorization": f"Bearer {token}"}, timeout=20)
    if p.status_code == 404:
        raise RuntimeError("This Microsoft account doesn't own Minecraft: Java Edition.")
    p.raise_for_status()
    p = p.json()
    return {"name": p["name"], "id": p["id"], "access_token": token, "refresh_token": refresh_token, "time": time.time()}


# ---------- instances ----------
def make_cb(emit):
    mx = {"v": 1}
    return {"setStatus": lambda t: emit(t, None),
            "setMax": lambda m: mx.__setitem__("v", m or 1),
            "setProgress": lambda p: emit(None, int(p * 100 / mx["v"]))}


def list_instances():
    return sorted(p.name for p in INST.iterdir() if (p / "instance.json").exists())


def get_instance(name):
    return json.loads((INST / name / "instance.json").read_text())


def _save_instance(name, mc, loader, version_id):
    d = INST / name
    (d / "mods").mkdir(parents=True, exist_ok=True)
    (d / "instance.json").write_text(json.dumps(
        {"name": name, "mc": mc, "loader": loader, "version_id": version_id}))


def delete_instance(name):
    shutil.rmtree(INST / name, ignore_errors=True)


def create_instance(name, mc, loader, emit):
    cb = make_cb(emit)
    prefetch_minecraft(mc, emit)
    mll.install.install_minecraft_version(mc, str(MC), callback=cb)
    vid = mc
    if loader in ("fabric", "quilt"):
        mod = getattr(mll, loader)
        lv = mod.get_latest_loader_version()
        getattr(mod, f"install_{loader}")(mc, str(MC), loader_version=lv, callback=cb)
        vid = f"{loader}-loader-{lv}-{mc}"
    _save_instance(name, mc, loader, vid)


# ---------- Modrinth ----------
def search(query, kind, mc=None, loader=None, sort="relevance", offset=0, limit=20):
    facets = [[f"project_type:{kind}"]]
    if kind in ("mod", "resourcepack", "shader") and mc:
        facets.append([f"versions:{mc}"])
    if kind == "mod" and loader in ("fabric", "quilt"):
        facets.append([f"categories:{loader}"])
    r = requests.get(f"{API}/search", headers=UA, timeout=20,
                     params={"query": query, "facets": json.dumps(facets), "limit": limit, "offset": offset, "index": sort})
    r.raise_for_status()
    j = r.json()
    return j["hits"], j.get("total_hits", len(j["hits"]))


def latest_version(pid, mc=None, loader=None):
    p = {}
    if mc:
        p["game_versions"] = json.dumps([mc])
    if loader:
        p["loaders"] = json.dumps([loader])
    r = requests.get(f"{API}/project/{pid}/version", params=p, headers=UA, timeout=20)
    r.raise_for_status()
    vs = r.json()
    return vs[0] if vs else None


_orig_request = requests.Session.request


def _request_with_timeout(self, *a, **k):
    if k.get("timeout") is None:
        k["timeout"] = (15, 60)  # also applies to requests made inside minecraft-launcher-lib
    return _orig_request(self, *a, **k)


requests.Session.request = _request_with_timeout
SESSION = requests.Session()
SESSION.headers.update(UA)
SESSION.mount("https://", requests.adapters.HTTPAdapter(pool_connections=32, pool_maxsize=32))


def _fetch(url, path, sha1=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if sha1 and path.exists() and hashlib.sha1(path.read_bytes()).hexdigest() == sha1:
        return path
    for attempt in range(3):
        try:
            h = hashlib.sha1()
            with SESSION.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(path, "wb") as o:
                    for chunk in r.iter_content(1 << 20):
                        o.write(chunk)
                        h.update(chunk)
            if sha1 and h.hexdigest() != sha1:
                raise IOError("download was corrupted")
            return path
        except Exception:
            if attempt == 2:
                raise


OS_NAME = "windows" if os.name == "nt" else "osx" if sys.platform == "darwin" else "linux"


def _rules_ok(rules):
    if not rules:
        return True
    ok = False
    for r in rules:
        o = r.get("os")
        if not o or o.get("name") in (None, OS_NAME):
            ok = r.get("action") == "allow"
    return ok


def _game_jobs(version):
    man = SESSION.get("https://piston-meta.mojang.com/mc/game/version_manifest_v2.json", timeout=20).json()
    entry = next((v for v in man["versions"] if v["id"] == version), None)
    if not entry:
        return []
    vj = SESSION.get(entry["url"], timeout=20).json()
    cj = vj["downloads"]["client"]
    jobs = [(cj["url"], MC / "versions" / version / f"{version}.jar", cj["sha1"])]
    for lib in vj.get("libraries", []):
        if not _rules_ok(lib.get("rules")):
            continue
        dl = lib.get("downloads", {})
        a = dl.get("artifact")
        if a and a.get("url"):
            jobs.append((a["url"], MC / "libraries" / a["path"], a["sha1"]))
        key = lib.get("natives", {}).get(OS_NAME)
        if key:
            cl = dl.get("classifiers", {}).get(key.replace("${arch}", "64"))
            if cl:
                jobs.append((cl["url"], MC / "libraries" / cl["path"], cl["sha1"]))
    ai = vj["assetIndex"]
    idx = MC / "assets" / "indexes" / f"{ai['id']}.json"
    _fetch(ai["url"], idx, ai["sha1"])
    for h in {o["hash"] for o in json.loads(idx.read_text())["objects"].values()}:
        jobs.append((f"https://resources.download.minecraft.net/{h[:2]}/{h}", MC / "assets" / "objects" / h[:2] / h, h))
    return jobs


def prefetch_minecraft(version, emit):
    """Download the game's files in parallel first; the library then only has to verify them."""
    try:
        emit("Reading version info…", None)
        pmap(lambda j: _fetch(*j), _game_jobs(version), emit, "Downloading game files", workers=32)
    except Exception as e:
        emit(f"Fast download skipped ({e}); using the standard installer", None)


def download(v, folder):
    f = next((x for x in v["files"] if x.get("primary")), v["files"][0])
    return _fetch(f["url"], Path(folder) / f["filename"], f.get("hashes", {}).get("sha1"))


def pmap(fn, items, emit, label, workers=16):
    """Run fn over items in parallel threads and report progress."""
    items = list(items)
    if not items:
        return
    done = 0
    with ThreadPoolExecutor(min(workers, len(items))) as ex:
        for fut in as_completed([ex.submit(fn, i) for i in items]):
            fut.result()
            done += 1
            emit(f"{label} {done}/{len(items)}", int(done * 100 / len(items)))


def install_mod(pid, inst, emit, version=None):
    m = get_instance(inst)
    loader = m["loader"] if m["loader"] in ("fabric", "quilt") else None
    plan, seen = [], set()

    def resolve(p, ver=None):
        if p in seen:
            return
        seen.add(p)
        v = ver or latest_version(p, m["mc"], loader)
        if not v:
            if not plan:
                raise RuntimeError(f"No version of this mod for {m['mc']} / {m['loader']}")
            return
        plan.append(v)
        for dep in v.get("dependencies", []):
            if dep.get("dependency_type") == "required" and dep.get("project_id"):
                resolve(dep["project_id"])
    emit("Resolving dependencies…", None)
    resolve(pid, version)
    pmap(lambda v: download(v, INST / inst / "mods"), plan, emit, "Downloading")


def install_modpack(pid, emit, version=None, icon_url=None):
    v = version or latest_version(pid)
    if not v:
        raise RuntimeError("Modpack has no downloadable version")
    emit("Downloading modpack", None)
    f = download(v, DATA / "tmp")
    name = _install_mrpack(f, emit)
    f.unlink(missing_ok=True)
    if icon_url:
        try:
            set_instance_icon(name, fetch_bytes(icon_url))
        except Exception:
            pass


def import_mrpack(path, emit):
    """Import a Modrinth .mrpack or a CurseForge modpack .zip."""
    import zipfile
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
    if "modrinth.index.json" not in names and "manifest.json" in names:
        _install_curseforge(Path(path), emit)
    else:
        _install_mrpack(Path(path), emit)


def classify(path):
    """Guess what a file is: modpack / mod / resourcepack / shader / None."""
    import zipfile
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".mrpack":
        return "modpack"
    if ext in (".jar", ".litemod"):
        return "mod"
    if ext == ".zip":
        try:
            with zipfile.ZipFile(p) as z:
                names = z.namelist()
                if "modrinth.index.json" in names:
                    return "modpack"
                if "manifest.json" in names and json.loads(z.read("manifest.json")).get("manifestType") == "minecraftModpack":
                    return "modpack"
                if "pack.mcmeta" in names:
                    return "resourcepack"
                if any(n.startswith("shaders/") for n in names):
                    return "shader"
        except Exception:
            pass
    return None


def _install_curseforge(f, emit):
    import zipfile
    from urllib.parse import unquote, urlparse
    with zipfile.ZipFile(f) as z:
        mf = json.loads(z.read("manifest.json"))
        mc = mf["minecraft"]["version"]
        loaders = mf["minecraft"].get("modLoaders", [])
        lid = next((x["id"] for x in loaders if x.get("primary")), loaders[0]["id"] if loaders else "")
        kind, _, lv = lid.partition("-")
        if kind == "neoforge":
            raise RuntimeError("This CurseForge pack needs NeoForge, which isn't supported yet. Try the Modrinth version of the pack.")
        name = "".join(ch for ch in mf.get("name", "") if ch not in '/\\:*?"<>|').strip() or "CurseForge pack"
        d = INST / name
        (d / "mods").mkdir(parents=True, exist_ok=True)
        cb = make_cb(emit)
        prefetch_minecraft(mc, emit)
        mll.install.install_minecraft_version(mc, str(MC), callback=cb)
        vid = mc
        if kind in ("fabric", "quilt"):
            getattr(getattr(mll, kind), "install_" + kind)(mc, str(MC), loader_version=lv, callback=cb)
            vid = f"{kind}-loader-{lv}-{mc}"
        elif kind == "forge":
            mll.forge.install_forge_version(f"{mc}-{lv}", str(MC), callback=cb)
            vid = mll.forge.forge_to_installed_version(f"{mc}-{lv}")
        failed = []

        def get(x):
            try:
                url = f"https://www.curseforge.com/api/v1/mods/{x['projectID']}/files/{x['fileID']}/download"
                with SESSION.get(url, stream=True, timeout=30, headers={"User-Agent": "Mozilla/5.0"}) as r:
                    r.raise_for_status()
                    fn = unquote(urlparse(r.url).path.rsplit("/", 1)[-1]) or f"{x['projectID']}-{x['fileID']}.jar"
                    with open(d / "mods" / Path(fn).name, "wb") as o:
                        for chunk in r.iter_content(1 << 20):
                            o.write(chunk)
            except Exception:
                failed.append(x)
        pmap(get, mf.get("files", []), emit, "Downloading mods")
        root, prefix = d.resolve(), mf.get("overrides", "overrides") + "/"
        for n in z.namelist():
            p = (d / n[len(prefix):]).resolve()
            if n.startswith(prefix) and not n.endswith("/") and root in p.parents:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(z.read(n))
    _save_instance(name, mc, "modpack", vid)
    if failed:
        (d / "MISSING_MODS.txt").write_text("Download these on curseforge.com and add them via Mods > Add from computer:\n" +
                                          "\n".join(f"https://www.curseforge.com/projects/{x['projectID']}  (file id {x['fileID']})" for x in failed))
        raise RuntimeError(f"Pack imported, but {len(failed)} mod(s) could not be downloaded automatically. "
                           "A list is in MISSING_MODS.txt inside the instance folder.")


def _install_mrpack(f, emit):
    import zipfile
    with zipfile.ZipFile(f) as z:
        idx = json.loads(z.read("modrinth.index.json"))
        deps, mc = idx.get("dependencies", {}), idx["dependencies"]["minecraft"]
        name = "".join(ch for ch in idx["name"] if ch not in '/\\:*?"<>|').strip() or "Modpack"
        d = INST / name
        d.mkdir(parents=True, exist_ok=True)
        cb = make_cb(emit)
        prefetch_minecraft(mc, emit)
        if "forge" in deps or "neoforge" in deps:  # these loaders: let the library do the whole install
            mll.mrpack.install_mrpack(str(f), str(MC), modpack_directory=str(d), callback=cb)
            vid = mll.mrpack.get_mrpack_launch_version(str(f))
        else:
            mll.install.install_minecraft_version(mc, str(MC), callback=cb)
            vid = mc
            for key, mod in (("fabric-loader", mll.fabric), ("quilt-loader", mll.quilt)):
                if key in deps:
                    getattr(mod, "install_" + key.split("-")[0])(mc, str(MC), loader_version=deps[key], callback=cb)
                    vid = f"{key}-{deps[key]}-{mc}"
            root = d.resolve()

            def get(x):
                p = (d / x["path"]).resolve()
                if root not in p.parents:
                    raise RuntimeError("Unsafe file path inside the modpack")
                _fetch(x["downloads"][0], p, x.get("hashes", {}).get("sha1"))
            pmap(get, [x for x in idx["files"] if x.get("env", {}).get("client") != "unsupported"], emit, "Downloading mods")
            for prefix in ("overrides/", "client-overrides/"):
                for n in z.namelist():
                    p = (d / n[len(prefix):]).resolve()
                    if n.startswith(prefix) and not n.endswith("/") and root in p.parents:
                        p.parent.mkdir(parents=True, exist_ok=True)
                        p.write_bytes(z.read(n))
    _save_instance(name, mc, "modpack", vid)
    return name


# ---------- Discord ----------
class Presence:
    def __init__(self, app_id):
        self.rpc = None
        if not app_id:
            return
        try:
            from pypresence import Presence as P
            self.rpc = P(app_id)
            self.rpc.connect()
        except Exception:
            self.rpc = None  # Discord not running / bad ID: just skip

    def set(self, details, state):
        try:
            if self.rpc:
                self.rpc.update(details=details, state=state, start=int(time.time()))
        except Exception:
            pass

    def stop(self):
        try:
            if self.rpc:
                self.rpc.clear()
                self.rpc.close()
        except Exception:
            pass


# ---------- play ----------
def play(name, cfg, emit):
    meta, d = get_instance(name), INST / name
    meta["last_played"] = time.time()
    (d / "instance.json").write_text(json.dumps(meta))
    acct = cfg.get("account")
    if not acct:
        raise RuntimeError("Sign in with your Microsoft account first (Account page).")
    try:
        acct = ms_refresh(cfg)
        cfg["account"] = acct
        save_cfg(cfg)
    except Exception:
        if time.time() - acct.get("time", 0) > 20 * 3600:
            raise RuntimeError("Your Microsoft session expired. Open Account > Change account and sign in again.")
        emit("Couldn't refresh the login, using the saved one", None)
    opts = {"username": acct["name"], "uuid": acct["id"], "token": acct["access_token"]}
    opts["gameDirectory"] = str(d)
    opts["jvmArguments"] = jvm_args(cfg, name, java_major(meta["version_id"], cfg.get("java_path", "")))
    if cfg.get("java_path"):
        opts["executablePath"] = cfg["java_path"]
    cmd = mll.command.get_minecraft_command(meta["version_id"], str(MC), opts)
    emit("Launching...", 100)
    env, wrapper, flags = launch_tweaks(cfg)
    started = time.time()
    log = open(d / "launcher-log.txt", "w", encoding="utf-8", errors="replace")
    log.write(f"Java: {cmd[0]}\nJVM args: {' '.join(opts['jvmArguments'])}\nWrapper: {wrapper}\nTweaks: OpenGL threading={perf_cfg(cfg)['gl_threading']}, dedicated GPU={perf_cfg(cfg)['dedicated_gpu']}\nVersion: {meta['version_id']}\n\n")
    log.flush()
    proc = subprocess.Popen(wrapper + cmd, cwd=d, env=env, stdout=log, stderr=subprocess.STDOUT, **flags)
    rpc = Presence(cfg["discord_app_id"])
    rpc.set(f"Playing {meta['name']}", f"Minecraft {meta['mc']} ({meta['loader']})")
    emit(f"Playing {name}", None)
    proc.wait()
    rpc.stop()
    log.close()
    return crash_report(d, proc.returncode, started)


# ---------- extras ----------
def fetch_bytes(url):
    import hashlib
    p = DATA / "icons" / hashlib.md5(url.encode()).hexdigest()
    p.parent.mkdir(exist_ok=True)
    if not p.exists():
        r = requests.get(url, headers=UA, timeout=15)
        r.raise_for_status()
        p.write_bytes(r.content)
    return p.read_bytes()


def list_mods(inst):
    return sorted(p.name for p in (INST / inst / "mods").glob("*.jar"))


def remove_mod(inst, filename):
    (INST / inst / "mods" / filename).unlink(missing_ok=True)


# ---------- versions, local files, skins ----------
def list_versions(pid, mc=None, loader=None, relax=False):
    def get(p):
        r = requests.get(f"{API}/project/{pid}/version", params=p, headers=UA, timeout=20)
        r.raise_for_status()
        return r.json()
    p = {}
    if mc:
        p["game_versions"] = json.dumps([mc])
    if loader in ("fabric", "quilt"):
        p["loaders"] = json.dumps([loader])
    vs = get(p)
    return vs if vs or not (relax and mc) else get({})  # packs often don't list every exact MC version


def add_mod_file(inst, src):
    d = INST / inst / "mods"
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, d / Path(src).name)


MCS = "https://api.minecraftservices.com/minecraft/profile"


def fresh_account(cfg):
    a = ms_refresh(cfg)
    cfg["account"] = a
    save_cfg(cfg)
    return a


def get_skin(cfg):
    a = fresh_account(cfg)
    r = requests.get(MCS, headers={"Authorization": f"Bearer {a['access_token']}"}, timeout=20)
    r.raise_for_status()
    s = next((x for x in r.json().get("skins", []) if x.get("state") == "ACTIVE"), None)
    return fetch_bytes(s["url"]) if s else None


def set_skin(cfg, png, variant):
    a = fresh_account(cfg)
    r = requests.post(MCS + "/skins", headers={"Authorization": f"Bearer {a['access_token']}"},
                      data={"variant": variant}, files={"file": ("skin.png", png, "image/png")}, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"Skin upload failed ({r.status_code}): {r.text[:200]}")


def player_skin(name):
    import base64
    r = requests.get(f"https://api.mojang.com/users/profiles/minecraft/{name}", headers=UA, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"Player '{name}' not found")
    r = requests.get(f"https://sessionserver.mojang.com/session/minecraft/profile/{r.json()['id']}", headers=UA, timeout=15)
    r.raise_for_status()
    tex = json.loads(base64.b64decode(r.json()["properties"][0]["value"]))["textures"].get("SKIN")
    if not tex:
        raise RuntimeError("That player has no custom skin")
    variant = "slim" if tex.get("metadata", {}).get("model") == "slim" else "classic"
    return requests.get(tex["url"], timeout=15).content, variant


# ---------- backgrounds, misc ----------
BG_USER = DATA / "backgrounds"
BG_EXT = {".png", ".jpg", ".jpeg", ".webp"}


def background_files():
    out = []
    for d in (ASSETS / "backgrounds", BG_USER):
        if d.exists():
            out += sorted(p for p in d.iterdir() if p.suffix.lower() in BG_EXT)
    return out


def add_background(src):
    BG_USER.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, BG_USER / Path(src).name)


def open_path(p):
    if os.name == "nt":
        os.startfile(str(p))
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(p)])


# ---------- resource packs & shaders ----------
SUBDIR = {"resourcepack": "resourcepacks", "shader": "shaderpacks"}


def install_pack(pid, inst, kind, emit, version=None):
    m = get_instance(inst)
    v = version or (list_versions(pid, m["mc"], None, relax=True) or [None])[0]
    if not v:
        raise RuntimeError("No downloadable version found")
    emit(f"Downloading {v['name']}", None)
    download(v, INST / inst / SUBDIR[kind])
    if kind == "shader" and m["loader"] in ("fabric", "quilt"):
        mods = INST / inst / "mods"
        if not any(w in p.name.lower() for p in mods.glob("*.jar") for w in ("iris", "optifine")):
            emit("Installing Iris (needed to run shaders)…", None)
            try:
                install_mod("iris", inst, emit)
            except Exception as e:
                emit(f"Couldn't install Iris automatically: {e}", None)


def list_files(inst, sub, exts):
    d = INST / inst / sub
    d.mkdir(parents=True, exist_ok=True)
    return sorted(p.name for p in d.iterdir() if p.suffix.lower() in exts or (p.is_dir() and sub != "mods"))


def add_file(inst, sub, src):
    d = INST / inst / sub
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, d / Path(src).name)


def remove_file(inst, sub, name):
    p = INST / inst / sub / name
    shutil.rmtree(p) if p.is_dir() else p.unlink(missing_ok=True)


def icon_path(name):
    return INST / name / "icon.png"


def set_instance_icon(name, data):
    icon_path(name).write_bytes(data)


# ---------- updates ----------
def _vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v))[:4]


def check_update():
    """Returns {'tag','url','notes'} if the latest GitHub release is newer than APP_VERSION, else None."""
    r = requests.get(f"https://api.github.com/repos/{REPO}/releases/latest", timeout=10,
                     headers={**UA, "Accept": "application/vnd.github+json"})
    if r.status_code == 404:  # no release published yet
        return None
    r.raise_for_status()
    j = r.json()
    tag = j.get("tag_name", "")
    if not _vtuple(tag) or _vtuple(tag) <= _vtuple(APP_VERSION):
        return None
    return {"tag": tag, "url": j.get("html_url"), "notes": (j.get("body") or "").strip()[:700]}


# ---------- performance ----------
PERF_DEFAULTS = {"ram_mode": "auto", "ram_mb": 4096, "profile": "balanced", "extra": "", "on_launch": "minimize",
                 "gamemode": True, "raise_priority": True, "gl_threading": False, "dedicated_gpu": False}
G1_FLAGS = ["-XX:+UseG1GC", "-XX:+ParallelRefProcEnabled", "-XX:MaxGCPauseMillis=50", "-XX:+UnlockExperimentalVMOptions",
            "-XX:G1NewSizePercent=20", "-XX:G1ReservePercent=20", "-XX:+PerfDisableSharedMem"]


def perf_cfg(cfg):
    p = dict(PERF_DEFAULTS)
    if "perf" not in cfg and cfg.get("ram_mb", 4096) != 4096:  # older versions stored one RAM value
        p.update(ram_mode="manual", ram_mb=cfg["ram_mb"])
    p.update(cfg.get("perf") or {})
    if (cfg.get("perf") or {}).get("schema", 1) < 2:
        p["gl_threading"] = False  # this option crashes some drivers, so it is off unless you switch it on again
    return p


def system_ram():
    """(total MB, available MB) of this PC."""
    try:
        if os.name == "nt":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong), ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong),
                            ("tpf", ctypes.c_ulonglong), ("apf", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong),
                            ("av", ctypes.c_ulonglong), ("ave", ctypes.c_ulonglong)]
            s = MS()
            s.l = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
            return s.tp // 2**20, s.ap // 2**20
        if sys.platform == "darwin":
            t = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"])) // 2**20
            return t, t // 2
        info = {k: int(v.split()[0]) // 1024 for k, v in (ln.split(":", 1) for ln in open("/proc/meminfo"))}
        return info["MemTotal"], info.get("MemAvailable", info["MemTotal"] // 2)
    except Exception:
        return 8192, 4096


def auto_ram_mb(inst, total, avail):
    """RAM that fits this instance: more mods/shaders need more, but too much only makes GC pauses longer."""
    mods = len(list((INST / inst / "mods").glob("*.jar")))
    base = 3072 if mods == 0 else 4096 if mods <= 40 else 6144 if mods <= 120 else 8192
    shaders = INST / inst / "shaderpacks"
    if shaders.exists() and any(shaders.iterdir()):
        base += 1024
    mc = _vtuple(get_instance(inst)["mc"])
    if mc[:2] and mc[:2] < (1, 13) and mods <= 40:
        base = min(base, 3072)  # old versions are light
    return int(max(1024, min(base, total * 0.6, avail - 1024, 12288)))


def pick_ram_mb(cfg, inst):
    p = perf_cfg(cfg)
    total, avail = system_ram()
    ram = p["ram_mb"] if p["ram_mode"] == "manual" else auto_ram_mb(inst, total, avail)
    return int(max(1024, min(ram, total * 0.85)) // 256 * 256)


@lru_cache(maxsize=8)
def _java_path_major(path):
    try:
        out = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=10).stderr
        m = re.search(r'version "(\d+)(?:\.(\d+))?', out)
        if m:
            return int(m.group(2)) if m.group(1) == "1" else int(m.group(1))
    except Exception:
        pass
    return 0


def java_major(version_id, java_path=""):
    if java_path and _java_path_major(java_path):
        return _java_path_major(java_path)
    vid = version_id
    for _ in range(3):  # loader versions point to the vanilla one with "inheritsFrom"
        try:
            j = json.loads((MC / "versions" / vid / f"{vid}.json").read_text())
        except Exception:
            break
        if "javaVersion" in j:
            return int(j["javaVersion"]["majorVersion"])
        vid = j.get("inheritsFrom")
        if not vid:
            break
    return 17


def jvm_args(cfg, inst, major):
    p = perf_cfg(cfg)
    ram = pick_ram_mb(cfg, inst)
    extra = shlex.split(p["extra"]) if p["extra"].strip() else []
    args = [] if any(a.startswith("-Xmx") for a in extra) else [f"-Xmx{ram}M", f"-Xms{min(ram, 2048)}M"]
    if p["profile"] == "zgc" and major >= 21:
        args += ["-XX:+UseZGC"] + (["-XX:+ZGenerational"] if major < 23 else [])
    elif p["profile"] == "serial":
        args += ["-XX:+UseSerialGC"]
    elif p["profile"] != "custom":  # balanced (also the fallback when ZGC isn't available)
        args += G1_FLAGS + [f"-XX:G1HeapRegionSize={'16M' if ram >= 3072 else '8M'}"]
    return args + extra


def launch_tweaks(cfg):
    """Environment, command wrapper and process flags that help the game run smoother."""
    p = perf_cfg(cfg)
    env, wrapper, kw = dict(os.environ), [], {}
    if p["gl_threading"]:
        env["__GL_THREADED_OPTIMIZATIONS"], env["mesa_glthread"] = "1", "true"
    else:  # force it off even if the desktop turns it on globally (it can hang the game on NVIDIA)
        env["__GL_THREADED_OPTIMIZATIONS"], env["mesa_glthread"] = "0", "false"
    if p["dedicated_gpu"] and os.name != "nt":
        env.update({"DRI_PRIME": "1", "__NV_PRIME_RENDER_OFFLOAD": "1", "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
                    "__VK_LAYER_NV_optimus": "NVIDIA_only"})
    if p["gamemode"] and sys.platform.startswith("linux") and shutil.which("gamemoderun"):
        wrapper = ["gamemoderun"]
    if os.name == "nt":
        kw["creationflags"] = 0x08000000 | (0x00008000 if p["raise_priority"] else 0)  # no console, above-normal priority
    return env, wrapper, kw


FPS_MODS = {"sodium": "sodium", "lithium": "lithium", "ferrite-core": "ferritecore", "modernfix": "modernfix",
            "immediatelyfast": "immediatelyfast", "entityculling": "entityculling"}


def install_fps_mods(inst, emit):
    mods = INST / inst / "mods"
    mods.mkdir(parents=True, exist_ok=True)
    done, skipped = [], []
    for slug, key in FPS_MODS.items():
        if any(key in p.name.lower().replace("-", "").replace("_", "") for p in mods.glob("*.jar")):
            skipped.append(f"{slug} (already installed)")
            continue
        try:
            emit(f"Installing {slug}…", None)
            install_mod(slug, inst, emit)
            done.append(slug)
        except Exception:
            skipped.append(f"{slug} (no version for this Minecraft version)")
    return ("Installed: " + (", ".join(done) or "nothing new") + ("\nSkipped: " + ", ".join(skipped) if skipped else ""))


# ---------- crash reports ----------
def crash_report(d, rc, started):
    """None if the game exited normally; otherwise a dict with a plain-language diagnosis and the log."""
    if rc in (0, None):
        return None
    try:
        lines = (d / "launcher-log.txt").read_text(errors="replace").splitlines()
    except Exception:
        lines = []
    tail = "\n".join(lines[-60:])
    low = tail.lower()
    fresh = lambda p: p.stat().st_mtime >= started - 5
    hs = sorted([p for p in d.glob("hs_err_pid*.log") if fresh(p)], key=lambda p: p.stat().st_mtime, reverse=True)
    cr = sorted([p for p in (d / "crash-reports").glob("crash-*.txt") if fresh(p)], key=lambda p: p.stat().st_mtime, reverse=True)
    hints, extra = [], ""
    watchdog = "watchdog" in low
    if cr:
        try:
            watchdog = watchdog or "Client shutdown" in cr[0].read_text(errors="replace")[:600]
        except Exception:
            pass
    if watchdog:
        hints.append("The game froze while CLOSING: Minecraft's shutdown watchdog ended it after the render thread got stuck in a graphics "
                     "call (usually the GPU driver or a rendering mod). Playing itself was fine. Make sure OpenGL threading is off, and if it "
                     "keeps happening, disable rendering helper mods such as Ixeris (Library > Mods > Disable / enable).")
    if "unrecognized vm option" in low or "could not create the java virtual machine" in low or "invalid maximum heap" in low:
        hints.append("Java refused one of the JVM flags or the memory amount. Press 'Apply safe settings' and try again.")
    if rc in (-9, 137) or "outofmemoryerror" in low or "java heap space" in low:
        hints.append("The game ran out of memory, or the system killed it because RAM was full. Use Auto memory or 4-6 GB.")
    if rc in (-11, 139, -6, 134, -1073741819) or hs:
        hints.append("A native crash (Java or the graphics driver). Turn off OpenGL threading and GameMode, update your GPU driver, and try again.")
    if hs:
        try:
            h = hs[0].read_text(errors="replace").splitlines()[:120]
            i = next((k for k, ln in enumerate(h) if "Problematic frame" in ln), None)
            if i is not None:
                extra += "Problematic frame: " + " ".join(x.lstrip("# ") for x in h[i + 1:i + 2]) + "\n"
        except Exception:
            pass
    if cr:
        try:
            desc = next((ln for ln in cr[0].read_text(errors="replace").splitlines() if ln.startswith("Description:")), "")
            extra += f"Crash report: {cr[0]}\n{desc}\n"
        except Exception:
            pass
    if "mixin" in low and ("failed" in low or "error" in low):
        hints.append("A mod failed to load (Mixin error). Remove the mod you added last.")
    if not hints:
        hints.append("No known cause found. Copy the report below and send it to me.")
    text = f"Exit code: {rc}\n" + extra + (f"JVM crash log: {hs[0]}\n" if hs else "") + "\nLast lines of the game log:\n" + tail
    return {"rc": rc, "hints": hints, "text": text, "folder": str(d)}


# ---------- in-game video settings presets ----------
VIDEO_PRESETS = {
    "fps": {"renderDistance": 8, "simulationDistance": 6, "entityDistanceScaling": 0.5, "particles": 2, "biomeBlendRadius": 1,
            "mipmapLevels": 1, "ao": "false", "graphicsMode": 0, "fancyGraphics": "false", "maxFps": 260},
    "balanced": {"renderDistance": 12, "simulationDistance": 8, "entityDistanceScaling": 0.75, "particles": 1, "biomeBlendRadius": 3,
                 "mipmapLevels": 2, "ao": "true", "graphicsMode": 1, "fancyGraphics": "true", "maxFps": 144},
    "quality": {"renderDistance": 16, "simulationDistance": 12, "entityDistanceScaling": 1.0, "particles": 0, "biomeBlendRadius": 5,
                "mipmapLevels": 4, "ao": "true", "graphicsMode": 1, "fancyGraphics": "true", "maxFps": 144},
}


def apply_video_preset(inst, key):
    """Edit options.txt: update the keys it already has (or write them all if the game never ran yet)."""
    p = INST / inst / "options.txt"
    want = {k: str(v) for k, v in VIDEO_PRESETS[key].items()}
    if p.exists():
        out = []
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            k = ln.split(":", 1)[0]
            out.append(f"{k}:{want[k]}" if k in want else ln)
    else:
        out = [f"{k}:{v}" for k, v in want.items()]
    p.write_text("\n".join(out) + "\n", encoding="utf-8")


def toggle_file(inst, sub, name):
    """Disable a mod by renaming it to .jar.disabled (the game ignores it), or enable it again."""
    p = INST / inst / sub / name
    q = p.with_name(name[:-9]) if name.endswith(".disabled") else p.with_name(name + ".disabled")
    p.rename(q)
    return q.name
