# ═══════════════════════════════════════════════════════════════════════════════
#  VRCST.py  –  VRC Scanner Tool  |  Kawaii Squad Studio
#  Improved: Settings panel, User/Avatar/World lookup, LocalDB stats,
#             OSC controls, session notes, quick-copy toolbar, theme engine,
#             clean imports, removed duplicate code, robust error handling.
# ═══════════════════════════════════════════════════════════════════════════════

# ── Standard library ──────────────────────────────────────────────────────────
import os, re, sys, shutil, datetime, time, psutil, logging, hashlib
import base64, json, subprocess, ctypes, requests, traceback, platform
import threading, webbrowser as wb, zipfile, getpass
from collections import defaultdict
from pathlib import Path
from urllib.request import Request
from http.cookiejar import LWPCookieJar
from io import BytesIO

# ── GUI ───────────────────────────────────────────────────────────────────────
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
from PIL import Image, ImageEnhance, ImageTk

# ── Third-party ───────────────────────────────────────────────────────────────
import pyfiglet
from colorama import Fore, Style, init as colorama_init
from rich.console import Console
from rich.text import Text
from rich.table import Table
from plyer import notification
from pypresence import Presence

try:
    from pythonosc import udp_client
    OSC_AVAILABLE = True
except ImportError:
    OSC_AVAILABLE = False

try:
    import UnityPy
    from UnityPy.helpers import TypeTreeHelper
    TypeTreeHelper.read_typetree_boost = False
    UNITYPY_AVAILABLE = True
except ImportError:
    UNITYPY_AVAILABLE = False

import vrchatapi
from vrchatapi.api import authentication_api
from vrchatapi.models.two_factor_auth_code import TwoFactorAuthCode
from vrchatapi.models.two_factor_email_code import TwoFactorEmailCode
from vrchatapi.rest import ApiException
from vrchatapi.api_client import ApiClient
from vrchatapi.configuration import Configuration

colorama_init(autoreset=True)

# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS & PATHS
# ══════════════════════════════════════════════════════════════════════════════
VERSION       = "2.3.0"
USER_AGENT    = "VRCST / Kawaii Squad Studio"
BASE_API      = "https://api.vrchat.cloud/api/1"
VRC_API       = "https://vrchat.com/api/1"
GITHUB_API    = "https://api.github.com/repos/Kawaii-Squad/VRCST/releases/latest"
AVTRDB_API    = "https://api.avtrdb.com/v1/avatar/search"

BANNER_URL    = "https://raw.githubusercontent.com/kawaiistudio/KSUnityTools/main/logo%20KS.png"
LOGO_URL      = "https://raw.githubusercontent.com/kawaiistudio/KSUnityTools/main/logo_v2.png"
WEBSITES_URL  = "https://raw.githubusercontent.com/kawaiistudio/VRCST/refs/heads/main/universalvrcwebsites.txt"

DISCORD_URL   = "https://discord.gg/xAeJrSAgqG"
TELEGRAM_URL  = "https://t.me/kawaiistudio"
VRCHAT_GROUP  = "https://vrchat.com/home/group/grp_7bf987ee-2f4a-4eae-b9b5-c060b97250ab"

USER_HOME     = os.path.expanduser("~")
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
LOCAL_DB      = os.path.join(BASE_DIR, "LocalDB")
TEMPS_DIR     = os.path.join(LOCAL_DB, "temps")
INFOS_DIR     = os.path.join(LOCAL_DB, "infos")
VRCA_DIR      = os.path.join(LOCAL_DB, "VRCA")
VRCW_DIR      = os.path.join(LOCAL_DB, "VRCW")
AUTH_PATH     = os.path.join(TEMPS_DIR, "AuthCookie.txt")
SETTINGS_PATH = os.path.join(LOCAL_DB, "settings.json")
NOTES_PATH    = os.path.join(LOCAL_DB, "session_notes.json")
CACHE_PATH    = os.path.join(USER_HOME, "AppData", "LocalLow",
                              "VRChat", "VRChat", "Cache-WindowsPlayer")
DOWNLOADS_DIR = Path.home() / "Downloads"

IP_OSC        = "127.0.0.1"
PORT_OSC      = 9000

# ══════════════════════════════════════════════════════════════════════════════
#  SETTINGS ENGINE
# ══════════════════════════════════════════════════════════════════════════════
DEFAULT_SETTINGS = {
    "theme":              "dark",          # dark | light | system
    "accent_color":       "#e94560",
    "discord_rpc":        True,
    "discord_client_id":  "1280110674240077916",
    "discord_rpc_detail": "Exploring VRChat",
    "console_visible":    True,
    "console_height":     100,
    "osc_enabled":        False,
    "osc_ip":             "127.0.0.1",
    "osc_port":           9000,
    "auto_save_friends":  False,
    "notify_on_capture":  True,
    "update_check":       True,
    "log_level":          "INFO",
    "window_width":       1100,
    "window_height":      800,
}

def load_settings() -> dict:
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH) as f:
                data = json.load(f)
            # Merge with defaults so new keys always exist
            merged = {**DEFAULT_SETTINGS, **data}
            return merged
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)

def save_settings(s: dict):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(s, f, indent=2)

SETTINGS = load_settings()

# ══════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════════════════
os.makedirs(TEMPS_DIR, exist_ok=True)
_log_level = getattr(logging, SETTINGS.get("log_level", "INFO"), logging.INFO)
logging.basicConfig(
    filename=os.path.join(TEMPS_DIR, "vrcst.log"),
    level=_log_level,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("VRCST")

# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def _hdrs(cookie: str | None = None) -> dict:
    h = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
    if cookie:
        h["Cookie"] = f"auth={cookie}"
    return h

def api_get(url: str, cookie: str | None = None, params: dict = None) -> requests.Response | None:
    try:
        return requests.get(url, headers=_hdrs(cookie), params=params or {}, timeout=12)
    except Exception as e:
        log.error(f"GET {url}: {e}")
        return None

def api_post(url: str, cookie: str | None = None, data: dict = None) -> requests.Response | None:
    try:
        return requests.post(url, headers=_hdrs(cookie), json=data or {}, timeout=12)
    except Exception as e:
        log.error(f"POST {url}: {e}")
        return None

def api_put(url: str, cookie: str | None = None, data: dict = None) -> requests.Response | None:
    try:
        return requests.put(url, headers=_hdrs(cookie), json=data or {}, timeout=12)
    except Exception as e:
        log.error(f"PUT {url}: {e}")
        return None

def notify(title: str, msg: str):
    try:
        if SETTINGS.get("notify_on_capture", True):
            notification.notify(title=title, message=msg, app_name="VRCST", timeout=8)
    except Exception:
        pass

def show_notification(title: str, msg: str):
    notify(title, msg)

def load_image_from_url(url: str, size=None, crop_to_fit=False) -> Image.Image | None:
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            img = Image.open(BytesIO(r.content))
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            if size and crop_to_fit:
                tw, th = size
                ratio = max(tw / img.width, th / img.height)
                img = img.resize((int(img.width*ratio), int(img.height*ratio)),
                                  Image.Resampling.LANCZOS)
                l = (img.width - tw) // 2
                t = (img.height - th) // 2
                img = img.crop((l, t, l+tw, t+th))
            elif size:
                img = img.resize(size, Image.Resampling.LANCZOS)
            return img
    except Exception as e:
        log.warning(f"load_image_from_url: {e}")
    return None

def create_directory(directory: str):
    os.makedirs(directory, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
#  AUTH COOKIE
# ══════════════════════════════════════════════════════════════════════════════
def get_auth_cookie(path: str = AUTH_PATH) -> str | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            for line in f:
                if "auth=" in line:
                    return line.split("auth=")[1].split(";")[0].strip()
    except Exception:
        pass
    return None

def save_auth_cookie(api_client, filename: str = AUTH_PATH):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    jar = LWPCookieJar(filename=filename)
    for c in api_client.rest_client.cookie_jar:
        jar.set_cookie(c)
    jar.save()

def load_auth_cookie(api_client, filename: str = AUTH_PATH):
    jar = LWPCookieJar(filename=filename)
    if os.path.exists(filename):
        try:
            jar.load()
        except Exception:
            jar.save()
    else:
        jar.save()
    for c in jar:
        api_client.rest_client.cookie_jar.set_cookie(c)

auth_cookie = get_auth_cookie()

# ══════════════════════════════════════════════════════════════════════════════
#  DISCORD RPC
# ══════════════════════════════════════════════════════════════════════════════
_CLIENT_ID       = SETTINGS.get("discord_client_id", DEFAULT_SETTINGS["discord_client_id"])
RPC              = Presence(_CLIENT_ID)
_vrchat_start    = None

def find_vrchat_process() -> bool:
    global _vrchat_start
    for p in psutil.process_iter(attrs=["pid","name","create_time"]):
        try:
            if "VRChat" in p.info["name"]:
                if _vrchat_start is None:
                    _vrchat_start = p.info["create_time"]
                return True
        except Exception:
            continue
    _vrchat_start = None
    return False

def update_rich_presence():
    if not SETTINGS.get("discord_rpc", True):
        return
    try:
        RPC.connect()
        log.info("Discord RPC connected.")
    except Exception as e:
        log.warning(f"Discord RPC connect failed: {e}")
        return
    detail = SETTINGS.get("discord_rpc_detail", "Exploring VRChat")
    while True:
        try:
            if find_vrchat_process() and _vrchat_start:
                elapsed = int(time.time() - _vrchat_start)
                m, s = divmod(elapsed, 60)
                RPC.update(state=f"VRChat open for {m:02}:{s:02}",
                           details=detail,
                           large_image="vrchat_logo", small_image="icon",
                           start=_vrchat_start)
            else:
                RPC.update(state="Waiting for VRChat",
                           details=detail,
                           large_image="vrchat_logo", small_image="icon")
        except Exception as e:
            log.warning(f"RPC update: {e}")
        time.sleep(15)

# ══════════════════════════════════════════════════════════════════════════════
#  UPDATE CHECKER
# ══════════════════════════════════════════════════════════════════════════════
def get_latest_release() -> dict | None:
    try:
        r = requests.get(GITHUB_API, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"⚠️ Could not fetch release info: {e}")
        return None

def _extract_version(tag: str) -> str | None:
    m = re.search(r"VRCSTVer\.\(([\d\.]+)\)", tag or "")
    return m.group(1) if m else None

def check_for_updates():
    if not SETTINGS.get("update_check", True):
        return
    release = get_latest_release()
    if not release:
        return
    latest = _extract_version(release.get("tag_name",""))
    if not latest:
        return
    print(f"📦 Installed: {VERSION}  |  Latest: {latest}")
    if VERSION != latest:
        print("🚀 Update available!")
        root = tk.Tk(); root.withdraw()
        want = messagebox.askyesno("Update Available",
            f"Version {latest} is available.\nDo you want to download it?")
        root.destroy()
        if want:
            assets = release.get("assets", [])
            if assets:
                url  = assets[0].get("browser_download_url")
                name = url.split("/")[-1]
                dest = DOWNLOADS_DIR / name
                print(f"⬇️ Downloading {name}…")
                try:
                    resp = requests.get(url, stream=True, timeout=60)
                    with open(dest, "wb") as f:
                        for chunk in resp.iter_content(8192):
                            f.write(chunk)
                    print(f"✅ Downloaded to {dest}")
                    wb.open(str(DOWNLOADS_DIR))
                except Exception as e:
                    print(f"⚠️ Download failed: {e}")
    else:
        print("👍 You are up to date.")

# ══════════════════════════════════════════════════════════════════════════════
#  VRCHAT API  –  UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════
def select_avatar(avatar_id: str, cookie: str | None = None) -> bool:
    c = cookie or auth_cookie
    r = api_put(f"{VRC_API}/avatars/{avatar_id}/select", c)
    if r and r.status_code == 200:
        print("\033[92mAvatar selected successfully.\033[0m")
        return True
    code = r.status_code if r else "?"
    print(f"\033[91mFailed to select avatar. Status: {code}\033[0m")
    return False

def invitemyselftocustuminstance(cookie: str, world_id: str, instance_id: str):
    url = f"{VRC_API}/invite/myself/to/{world_id}:{instance_id}"
    r   = api_post(url, cookie)
    if r and r.status_code == 200:
        print("\033[92mSuccessfully sent invite request.\033[0m")
    else:
        code = r.status_code if r else "?"
        print(f"\033[91mFailed to send invite. Status: {code}\033[0m")

def extract_world_and_instance_id(url: str) -> tuple:
    m = re.search(r"worldId=([^&]+)&instanceId=([^&]+)", url)
    if m:
        return m.group(1), m.group(2)
    # Also handle vrchat:// style links
    m2 = re.search(r"(wrld_[^:&\s]+)[:%]([\w~!]+)", url)
    if m2:
        return m2.group(1), m2.group(2)
    return None, None

def get_user_profile(user_id: str, cookie: str | None = None) -> dict | None:
    """Fetch any user's public profile by ID."""
    c = cookie or auth_cookie
    r = api_get(f"{BASE_API}/users/{user_id}", c)
    return r.json() if r and r.status_code == 200 else None

def get_avatar_info(avatar_id: str, cookie: str | None = None) -> dict | None:
    c = cookie or auth_cookie
    r = api_get(f"{BASE_API}/avatars/{avatar_id}", c)
    return r.json() if r and r.status_code == 200 else None

def get_world_info(world_id: str, cookie: str | None = None) -> dict | None:
    c = cookie or auth_cookie
    r = api_get(f"{BASE_API}/worlds/{world_id}", c)
    return r.json() if r and r.status_code == 200 else None

def get_self(cookie: str | None = None) -> dict | None:
    c = cookie or auth_cookie
    r = api_get(f"{BASE_API}/auth/user", c)
    return r.json() if r and r.status_code == 200 else None

def save_friends_list(auth_api, cookie: str):
    try:
        user = auth_api.get_current_user()
        name = user.display_name
        r    = api_get(f"{BASE_API}/auth/user/friends", cookie,
                        params={"n": 100, "offline": "false"})
        if r and r.status_code == 200:
            path = os.path.join(INFOS_DIR, f"friendlist_{name}.json")
            os.makedirs(INFOS_DIR, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(r.json(), f, ensure_ascii=False, indent=2)
            print(f"\033[92mFriend list saved to {path}\033[0m")
    except Exception as e:
        log.error(f"save_friends_list: {e}")

# ══════════════════════════════════════════════════════════════════════════════
#  OSC
# ══════════════════════════════════════════════════════════════════════════════
def send_osc(address: str, value):
    if not OSC_AVAILABLE:
        print("[OSC] pythonosc not installed.")
        return
    if not SETTINGS.get("osc_enabled", False):
        print("[OSC] OSC is disabled in Settings.")
        return
    try:
        client = udp_client.SimpleUDPClient(
            SETTINGS.get("osc_ip", IP_OSC),
            int(SETTINGS.get("osc_port", PORT_OSC)))
        client.send_message(address, value)
        print(f"[OSC] Sent {address} = {value}")
    except Exception as e:
        print(f"[OSC] Error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
#  LOCAL DB STATS
# ══════════════════════════════════════════════════════════════════════════════
def get_localdb_stats() -> dict:
    stats = {"vrca_count": 0, "vrcw_count": 0,
             "vrca_size_mb": 0.0, "vrcw_size_mb": 0.0,
             "avatars_info": 0, "worlds_info": 0,
             "private_avatars": 0, "private_worlds": 0}
    try:
        if os.path.isdir(VRCA_DIR):
            files = [f for f in os.listdir(VRCA_DIR) if f.endswith(".vrca")]
            stats["vrca_count"] = len(files)
            stats["vrca_size_mb"] = round(
                sum(os.path.getsize(os.path.join(VRCA_DIR, f)) for f in files) / 1_048_576, 1)
        if os.path.isdir(VRCW_DIR):
            files = [f for f in os.listdir(VRCW_DIR) if f.endswith(".vrcw")]
            stats["vrcw_count"] = len(files)
            stats["vrcw_size_mb"] = round(
                sum(os.path.getsize(os.path.join(VRCW_DIR, f)) for f in files) / 1_048_576, 1)
        for fname, key_total, key_private in [
                ("INFO_VRCA.json", "avatars_info", "private_avatars"),
                ("INFO_VRCW.json", "worlds_info",  "private_worlds")]:
            p = os.path.join(INFOS_DIR, fname)
            if os.path.exists(p):
                with open(p) as f:
                    data = json.load(f)
                stats[key_total]   = len(data)
                stats[key_private] = sum(1 for x in data if x.get("status") == "private")
    except Exception as e:
        log.warning(f"get_localdb_stats: {e}")
    return stats

# ══════════════════════════════════════════════════════════════════════════════
#  NOTES
# ══════════════════════════════════════════════════════════════════════════════
def load_notes() -> list:
    if os.path.exists(NOTES_PATH):
        try:
            with open(NOTES_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_notes(notes: list):
    os.makedirs(os.path.dirname(NOTES_PATH), exist_ok=True)
    with open(NOTES_PATH, "w") as f:
        json.dump(notes, f, indent=2)

# ══════════════════════════════════════════════════════════════════════════════
#  SUBSCRIPT LAUNCHER HELPER
# ══════════════════════════════════════════════════════════════════════════════
def _launch_subscript(script_name: str, window_title: str, *extra_args):
    path = os.path.join(BASE_DIR, "Dependencies", "subscripts", script_name)
    if not os.path.isfile(path):
        print(f"[ERROR] Script not found: {path}")
        return
    if os.name == "nt":
        args_str = " ".join(f'"{a}"' for a in extra_args)
        cmd = (f'start "{window_title}" cmd /k '
               f'"cd /d "{BASE_DIR}" && "{sys.executable}" "{path}" {args_str}"')
        subprocess.Popen(cmd, shell=True)
    else:
        subprocess.Popen(
            ["x-terminal-emulator", "-e", sys.executable, path, *extra_args],
            cwd=BASE_DIR)
    print(f"Launched: {script_name}")

def autoinvitegroup():         _launch_subscript("autoinvitegroup.py",  "Auto Invite Group")
def launch_friendlistrecovery():_launch_subscript("friendlistsaver.py",  "Friendlist Recovery")
def launch_networkdb_manager(): _launch_subscript("NetworkDB.py",        "Network DB Manager")
def launch_loggerscript():      _launch_subscript("loggerscript.py",     "Logger Script")
def launch_group_id_logger():   _launch_subscript("GroupIDLogger.py",    "GroupID Logger")
def run_asset_ripper():         _launch_subscript("AssetRipper.py",      "Asset Ripper")
def launch_universal_asset_viewer(): _launch_subscript("UniversalAssetViewer.py","Universal Asset Viewer")

# ══════════════════════════════════════════════════════════════════════════════
#  GUI  –  SETTINGS PANEL
# ══════════════════════════════════════════════════════════════════════════════
class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent, on_save_callback=None):
        super().__init__(parent)
        self.title("⚙ Settings  –  VRCST")
        self.geometry("620x680")
        self.resizable(False, False)
        self.configure(fg_color="#0d0d1a")
        self.attributes("-topmost", True)
        self._cb = on_save_callback
        self._vars = {}
        self._build()

    def _build(self):
        tabs = ctk.CTkTabview(self, fg_color="#111122", corner_radius=12)
        tabs.pack(fill="both", expand=True, padx=16, pady=16)

        for name in ("Appearance", "Discord RPC", "OSC", "Network", "Advanced"):
            tabs.add(name)

        self._tab_appearance(tabs.tab("Appearance"))
        self._tab_discord(tabs.tab("Discord RPC"))
        self._tab_osc(tabs.tab("OSC"))
        self._tab_network(tabs.tab("Network"))
        self._tab_advanced(tabs.tab("Advanced"))

        ctk.CTkButton(self, text="💾  Save Settings", height=42,
                      fg_color="#2CC985", hover_color="#1fa36a",
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=self._save).pack(padx=16, pady=(0, 16), fill="x")

    # ── Appearance ─────────────────────────────────────────────────────────
    def _tab_appearance(self, frame):
        self._row(frame, "Theme", "theme",
                  ["dark","light","system"], SETTINGS["theme"])
        self._entry_row(frame, "Accent Colour (hex)", "accent_color",
                         SETTINGS["accent_color"])
        self._check_row(frame, "Show console panel", "console_visible",
                         SETTINGS["console_visible"])
        self._slider_row(frame, "Console height (px)", "console_height",
                          SETTINGS["console_height"], 60, 300)

    # ── Discord RPC ────────────────────────────────────────────────────────
    def _tab_discord(self, frame):
        self._check_row(frame, "Enable Discord Rich Presence", "discord_rpc",
                         SETTINGS["discord_rpc"])
        self._entry_row(frame, "Discord Client ID", "discord_client_id",
                         SETTINGS["discord_client_id"])
        self._entry_row(frame, "RPC Detail text", "discord_rpc_detail",
                         SETTINGS["discord_rpc_detail"])

    # ── OSC ────────────────────────────────────────────────────────────────
    def _tab_osc(self, frame):
        self._check_row(frame, "Enable OSC output", "osc_enabled",
                         SETTINGS["osc_enabled"])
        self._entry_row(frame, "OSC IP address", "osc_ip",
                         SETTINGS["osc_ip"])
        self._entry_row(frame, "OSC Port", "osc_port",
                         str(SETTINGS["osc_port"]))

        ctk.CTkLabel(frame, text="Quick OSC Actions:",
                     text_color="#8888aa").pack(anchor="w", padx=16, pady=(10,2))
        bf = ctk.CTkFrame(frame, fg_color="transparent")
        bf.pack(fill="x", padx=16)
        for label, addr, val in [
            ("Mute",     "/avatar/parameters/Mute",       True),
            ("Unmute",   "/avatar/parameters/Mute",       False),
            ("Afk On",   "/avatar/parameters/AFK",        True),
            ("Afk Off",  "/avatar/parameters/AFK",        False),
        ]:
            ctk.CTkButton(bf, text=label, width=100, height=30,
                          fg_color="#252540", hover_color="#353560",
                          command=lambda a=addr, v=val: send_osc(a, v)
                          ).pack(side="left", padx=4, pady=4)

    # ── Network ────────────────────────────────────────────────────────────
    def _tab_network(self, frame):
        self._check_row(frame, "Check for updates on startup", "update_check",
                         SETTINGS["update_check"])
        self._check_row(frame, "Show desktop notifications", "notify_on_capture",
                         SETTINGS["notify_on_capture"])
        self._check_row(frame, "Auto-save friend list on login", "auto_save_friends",
                         SETTINGS["auto_save_friends"])

    # ── Advanced ───────────────────────────────────────────────────────────
    def _tab_advanced(self, frame):
        self._row(frame, "Log level", "log_level",
                  ["DEBUG","INFO","WARNING","ERROR"], SETTINGS["log_level"])
        ctk.CTkButton(frame, text="🗑  Clear LocalDB temps",
                      fg_color="#e74c3c", hover_color="#c0392b",
                      command=self._clear_temps
                      ).pack(padx=16, pady=8, fill="x")
        ctk.CTkButton(frame, text="📂  Open LocalDB folder",
                      fg_color="#34495e", hover_color="#2c3e50",
                      command=lambda: wb.open(LOCAL_DB)
                      ).pack(padx=16, pady=4, fill="x")
        ctk.CTkButton(frame, text="📋  Open log file",
                      fg_color="#34495e", hover_color="#2c3e50",
                      command=lambda: wb.open(os.path.join(TEMPS_DIR,"vrcst.log"))
                      ).pack(padx=16, pady=4, fill="x")

    # ── Widget builders ────────────────────────────────────────────────────
    def _row(self, frame, label, key, options, current):
        r = ctk.CTkFrame(frame, fg_color="transparent")
        r.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(r, text=label, width=200, anchor="w",
                     text_color="#ccccdd").pack(side="left")
        var = ctk.StringVar(value=current)
        self._vars[key] = var
        ctk.CTkOptionMenu(r, variable=var, values=options, width=160).pack(side="right")

    def _check_row(self, frame, label, key, current):
        r = ctk.CTkFrame(frame, fg_color="transparent")
        r.pack(fill="x", padx=16, pady=6)
        var = ctk.BooleanVar(value=current)
        self._vars[key] = var
        ctk.CTkCheckBox(r, text=label, variable=var,
                        text_color="#ccccdd").pack(side="left")

    def _entry_row(self, frame, label, key, current):
        r = ctk.CTkFrame(frame, fg_color="transparent")
        r.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(r, text=label, width=200, anchor="w",
                     text_color="#ccccdd").pack(side="left")
        var = ctk.StringVar(value=current)
        self._vars[key] = var
        ctk.CTkEntry(r, textvariable=var, width=220).pack(side="right")

    def _slider_row(self, frame, label, key, current, lo, hi):
        r = ctk.CTkFrame(frame, fg_color="transparent")
        r.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(r, text=label, width=200, anchor="w",
                     text_color="#ccccdd").pack(side="left")
        var = ctk.IntVar(value=int(current))
        self._vars[key] = var
        ctk.CTkSlider(r, from_=lo, to=hi, variable=var, width=180).pack(side="right")

    def _save(self):
        for key, var in self._vars.items():
            val = var.get()
            if key == "osc_port":
                try:    val = int(val)
                except: val = 9000
            SETTINGS[key] = val
        save_settings(SETTINGS)
        # Apply theme immediately
        ctk.set_appearance_mode(SETTINGS["theme"])
        print("[Settings] Saved.")
        if self._cb:
            self._cb()
        self.destroy()

    def _clear_temps(self):
        for f in os.listdir(TEMPS_DIR):
            if f.endswith(".log") or f == "progress.txt":
                try:
                    os.remove(os.path.join(TEMPS_DIR, f))
                except Exception:
                    pass
        print("[Settings] Temp files cleared.")

# ══════════════════════════════════════════════════════════════════════════════
#  GUI  –  USER / AVATAR / WORLD LOOKUP
# ══════════════════════════════════════════════════════════════════════════════
class LookupWindow(ctk.CTkToplevel):
    """Universal lookup: paste a usr_/avtr_/wrld_ ID and get full info."""
    def __init__(self, parent, cookie: str | None = None, prefill: str = ""):
        super().__init__(parent)
        self.title("🔎 ID Lookup")
        self.geometry("700x540")
        self.configure(fg_color="#0d0d1a")
        self.attributes("-topmost", True)
        self.cookie = cookie
        self._build(prefill)

    def _build(self, prefill: str):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=12)

        self.entry = ctk.CTkEntry(top, placeholder_text="Paste usr_ / avtr_ / wrld_ ID here",
                                   height=40, font=ctk.CTkFont(size=13))
        self.entry.pack(side="left", fill="x", expand=True, padx=(0,8))
        if prefill:
            self.entry.insert(0, prefill)

        ctk.CTkButton(top, text="Look up", height=40, width=90,
                      fg_color="#e94560", hover_color="#c13550",
                      command=self._lookup).pack(side="left")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="#111122", corner_radius=10)
        self.scroll.pack(fill="both", expand=True, padx=16, pady=(0,16))

        self.status = ctk.CTkLabel(self.scroll, text="Enter an ID and click Look up.",
                                    text_color="#8888aa")
        self.status.pack(pady=40)

        self.entry.bind("<Return>", lambda _: self._lookup())

    def _lookup(self):
        vid = self.entry.get().strip()
        for w in self.scroll.winfo_children():
            w.destroy()
        if not vid:
            return
        self._show_loading()
        threading.Thread(target=self._fetch, args=(vid,), daemon=True).start()

    def _show_loading(self):
        ctk.CTkLabel(self.scroll, text="⌛ Fetching…",
                     text_color="#00adb5").pack(pady=40)

    def _fetch(self, vid: str):
        data = None
        kind = None
        if vid.startswith("usr_"):
            data = get_user_profile(vid, self.cookie)
            kind = "user"
        elif vid.startswith("avtr_"):
            data = get_avatar_info(vid, self.cookie)
            kind = "avatar"
        elif vid.startswith("wrld_"):
            data = get_world_info(vid, self.cookie)
            kind = "world"
        self.after(0, lambda: self._display(data, kind, vid))

    def _display(self, data: dict | None, kind: str | None, vid: str):
        for w in self.scroll.winfo_children():
            w.destroy()
        if not data:
            ctk.CTkLabel(self.scroll, text="❌ Not found or private.",
                         text_color="#e94560").pack(pady=40)
            return

        # Image
        img_url = (data.get("userIcon") or data.get("profilePicOverride") or
                   data.get("imageUrl") or data.get("thumbnailImageUrl") or "")
        if img_url:
            threading.Thread(target=self._load_thumb, args=(img_url,), daemon=True).start()

        # Key fields
        fields = {
            "user":   ["id","displayName","status","statusDescription",
                       "bio","location","last_login","date_joined",
                       "friendCount","followerCount","following"],
            "avatar": ["id","name","description","releaseStatus",
                       "authorName","authorId","unityVersion","platform","updated_at"],
            "world":  ["id","name","description","capacity","occupants",
                       "authorName","releaseStatus","visits","popularity",
                       "heat","tags","updated_at"],
        }.get(kind, list(data.keys())[:20])

        for key in fields:
            val = data.get(key, "")
            if val in (None, "", [], {}):
                continue
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val[:8])
            row = ctk.CTkFrame(self.scroll, fg_color="#1a1a2e", corner_radius=8)
            row.pack(fill="x", padx=8, pady=3)
            ctk.CTkLabel(row, text=str(key), width=160, anchor="w",
                         text_color="#00adb5",
                         font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=8)
            ctk.CTkLabel(row, text=str(val)[:120], anchor="w",
                         text_color="#e0e0f0",
                         font=ctk.CTkFont(size=12), wraplength=440).pack(side="left", padx=4)

        # Copy ID button
        ctk.CTkButton(self.scroll, text=f"📋 Copy ID: {vid}",
                      fg_color="#252540", hover_color="#353560",
                      command=lambda: (self.clipboard_clear(), self.clipboard_append(vid))
                      ).pack(pady=8, padx=8)

        if kind == "world":
            ctk.CTkButton(self.scroll, text="🌐 Open World",
                          fg_color="#3498db", hover_color="#2980b9",
                          command=lambda: wb.open(f"https://vrchat.com/home/world/{vid}")
                          ).pack(pady=4, padx=8)

    def _load_thumb(self, url: str):
        img = load_image_from_url(url, size=(200, 130), crop_to_fit=True)
        if img:
            cimg = ctk.CTkImage(light_image=img, dark_image=img, size=(200, 130))
            self.after(0, lambda: self._show_thumb(cimg))

    def _show_thumb(self, cimg):
        lbl = ctk.CTkLabel(self.scroll, image=cimg, text="",
                           corner_radius=10)
        lbl.pack(pady=(8, 4))

# ══════════════════════════════════════════════════════════════════════════════
#  GUI  –  LOCAL DB STATS PANEL
# ══════════════════════════════════════════════════════════════════════════════
class LocalDBWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("💾 Local Database")
        self.geometry("640x520")
        self.configure(fg_color="#0d0d1a")
        self.attributes("-topmost", True)
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="💾  Local Database",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color="#e94560").pack(pady=(16, 4))

        stats = get_localdb_stats()
        info_rows = [
            ("VRCA files",    f"{stats['vrca_count']}  ({stats['vrca_size_mb']} MB)"),
            ("VRCW files",    f"{stats['vrcw_count']}  ({stats['vrcw_size_mb']} MB)"),
            ("Avatar info",   f"{stats['avatars_info']} entries  ({stats['private_avatars']} private)"),
            ("World info",    f"{stats['worlds_info']} entries  ({stats['private_worlds']} private)"),
        ]
        for label, val in info_rows:
            r = ctk.CTkFrame(self, fg_color="#1a1a2e", corner_radius=8)
            r.pack(fill="x", padx=20, pady=4)
            ctk.CTkLabel(r, text=label, width=180, anchor="w",
                         text_color="#00adb5",
                         font=ctk.CTkFont(weight="bold")).pack(side="left", padx=12, pady=8)
            ctk.CTkLabel(r, text=val, text_color="#e0e0f0").pack(side="left")

        ctk.CTkLabel(self, text="ID Lookup in LocalDB:",
                     text_color="#8888aa",
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20, pady=(14,2))
        sf = ctk.CTkFrame(self, fg_color="transparent")
        sf.pack(fill="x", padx=20)
        self.id_entry = ctk.CTkEntry(sf, placeholder_text="avtr_… or wrld_…", height=36)
        self.id_entry.pack(side="left", fill="x", expand=True, padx=(0,8))
        ctk.CTkButton(sf, text="Search", height=36, width=80,
                      fg_color="#e94560", hover_color="#c13550",
                      command=self._search_local).pack(side="left")

        self.result = ctk.CTkTextbox(self, height=140, fg_color="#0a0a15",
                                      text_color="#00ff88",
                                      font=("Consolas", 11))
        self.result.pack(fill="x", padx=20, pady=(8,4))
        self.result.configure(state="disabled")

        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(fill="x", padx=20, pady=8)
        for text, cmd in [
            ("📂 Open VRCA folder", lambda: wb.open(VRCA_DIR)),
            ("📂 Open VRCW folder", lambda: wb.open(VRCW_DIR)),
            ("📂 Open infos folder", lambda: wb.open(INFOS_DIR)),
        ]:
            ctk.CTkButton(bf, text=text, height=34,
                          fg_color="#252540", hover_color="#353560",
                          command=cmd).pack(side="left", padx=4)

    def _search_local(self):
        sid = self.id_entry.get().strip()
        self.result.configure(state="normal")
        self.result.delete("1.0", "end")
        if not sid:
            self.result.insert("end", "Enter an ID.")
            self.result.configure(state="disabled")
            return

        if sid.startswith("avtr_"):
            ref_file = os.path.join(INFOS_DIR, "ID_REF_VRCA.json")
            asset_dir, ext = VRCA_DIR, ".vrca"
        elif sid.startswith("wrld_"):
            ref_file = os.path.join(INFOS_DIR, "ID_REF_VRCW.json")
            asset_dir, ext = VRCW_DIR, ".vrcw"
        else:
            self.result.insert("end", "Invalid ID format.")
            self.result.configure(state="disabled")
            return

        found = False
        if os.path.exists(ref_file):
            try:
                with open(ref_file) as f:
                    data = json.load(f)
                for h, ids in data.items():
                    if sid in ids:
                        asset = os.path.join(asset_dir, f"{sid}{ext}")
                        exists = os.path.isfile(asset)
                        self.result.insert("end",
                            f"✅ Found!\nHash : {h}\n"
                            f"File : {asset}\n"
                            f"Exists on disk: {exists}\n")
                        found = True
                        break
            except Exception as e:
                self.result.insert("end", f"Error reading ref file: {e}\n")

        if not found:
            self.result.insert("end", f"❌ {sid} not found in local DB.\n")
        self.result.configure(state="disabled")

# ══════════════════════════════════════════════════════════════════════════════
#  GUI  –  SESSION NOTES
# ══════════════════════════════════════════════════════════════════════════════
class NotesWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("📝 Session Notes")
        self.geometry("540x500")
        self.configure(fg_color="#0d0d1a")
        self.attributes("-topmost", True)
        self.notes = load_notes()
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="📝  Session Notes",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color="#e94560").pack(pady=(14, 4))
        ctk.CTkLabel(self, text="Quick notes – avatar IDs, world links, anything.",
                     text_color="#8888aa", font=ctk.CTkFont(size=11)).pack()

        inp_fr = ctk.CTkFrame(self, fg_color="transparent")
        inp_fr.pack(fill="x", padx=16, pady=8)
        self.new_entry = ctk.CTkEntry(inp_fr, placeholder_text="Type a note…", height=36)
        self.new_entry.pack(side="left", fill="x", expand=True, padx=(0,6))
        ctk.CTkButton(inp_fr, text="Add", height=36, width=60,
                      fg_color="#2CC985", hover_color="#1fa36a",
                      command=self._add).pack(side="left")
        self.new_entry.bind("<Return>", lambda _: self._add())

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="#111122", corner_radius=10)
        self.scroll.pack(fill="both", expand=True, padx=16, pady=(0,8))
        self._refresh()

        ctk.CTkButton(self, text="💾 Save & Close", height=38,
                      fg_color="#e94560", hover_color="#c13550",
                      command=self._save_close).pack(padx=16, pady=(0,12), fill="x")

    def _refresh(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        for i, note in enumerate(self.notes):
            row = ctk.CTkFrame(self.scroll, fg_color="#1a1a2e", corner_radius=8)
            row.pack(fill="x", pady=3)
            ts   = note.get("ts", "")
            text = note.get("text", "")
            ctk.CTkLabel(row, text=f"[{ts}]", width=140, anchor="w",
                         text_color="#8888aa",
                         font=ctk.CTkFont(size=10)).pack(side="left", padx=8)
            ctk.CTkLabel(row, text=text, anchor="w",
                         text_color="#e0e0f0",
                         font=ctk.CTkFont(size=12), wraplength=280).pack(side="left", padx=4)
            ctk.CTkButton(row, text="✕", width=28, height=24,
                          fg_color="#e74c3c", hover_color="#c0392b",
                          command=lambda idx=i: self._delete(idx)).pack(side="right", padx=6)
            # Copy button
            ctk.CTkButton(row, text="📋", width=28, height=24,
                          fg_color="#252540", hover_color="#353560",
                          command=lambda t=text: (self.clipboard_clear(),
                                                   self.clipboard_append(t))
                          ).pack(side="right", padx=2)

    def _add(self):
        txt = self.new_entry.get().strip()
        if not txt:
            return
        self.notes.append({"ts": datetime.datetime.now().strftime("%m/%d %H:%M"),
                            "text": txt})
        self.new_entry.delete(0, "end")
        self._refresh()

    def _delete(self, idx: int):
        self.notes.pop(idx)
        self._refresh()

    def _save_close(self):
        save_notes(self.notes)
        self.destroy()

# ══════════════════════════════════════════════════════════════════════════════
#  GUI  –  OSC CONTROL PANEL
# ══════════════════════════════════════════════════════════════════════════════
class OSCPanel(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("🎛 OSC Controls")
        self.geometry("480x420")
        self.configure(fg_color="#0d0d1a")
        self.attributes("-topmost", True)
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="🎛  OSC Controls",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color="#e94560").pack(pady=(14, 2))

        if not OSC_AVAILABLE:
            ctk.CTkLabel(self,
                text="⚠ pythonosc not installed.\npip install python-osc",
                text_color="#f0c040").pack(pady=20)
            return
        if not SETTINGS.get("osc_enabled", False):
            ctk.CTkLabel(self,
                text="OSC is disabled.\nEnable it in Settings → OSC.",
                text_color="#f0c040").pack(pady=20)

        quick = [
            ("🔇 Mute",       "/avatar/parameters/Mute",       True),
            ("🔊 Unmute",     "/avatar/parameters/Mute",       False),
            ("💤 AFK On",     "/avatar/parameters/AFK",        True),
            ("✅ AFK Off",    "/avatar/parameters/AFK",        False),
            ("😀 Emote 1",    "/avatar/parameters/VRCEmote",   1),
            ("😄 Emote 2",    "/avatar/parameters/VRCEmote",   2),
        ]
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(padx=16, pady=10)
        for i, (label, addr, val) in enumerate(quick):
            ctk.CTkButton(grid, text=label, width=130, height=40,
                          fg_color="#252550", hover_color="#353570",
                          command=lambda a=addr, v=val: send_osc(a, v)
                          ).grid(row=i//2, column=i%2, padx=6, pady=6)

        ctk.CTkLabel(self, text="Custom OSC message:",
                     text_color="#8888aa").pack(anchor="w", padx=16, pady=(10,2))
        cf = ctk.CTkFrame(self, fg_color="transparent")
        cf.pack(fill="x", padx=16)
        self.addr_e = ctk.CTkEntry(cf, placeholder_text="/avatar/parameters/…", width=220)
        self.addr_e.pack(side="left", padx=(0,6))
        self.val_e  = ctk.CTkEntry(cf, placeholder_text="value", width=80)
        self.val_e.pack(side="left", padx=(0,6))
        ctk.CTkButton(cf, text="Send", height=34, width=70,
                      fg_color="#e94560", hover_color="#c13550",
                      command=self._custom_send).pack(side="left")

    def _custom_send(self):
        addr = self.addr_e.get().strip()
        raw  = self.val_e.get().strip()
        if not addr:
            return
        # Try int, then float, then bool, then string
        val: bool | int | float | str
        if raw.lower() in ("true","1"):    val = True
        elif raw.lower() in ("false","0"): val = False
        else:
            try:    val = int(raw)
            except Exception:
                try:    val = float(raw)
                except Exception: val = raw
        send_osc(addr, val)

# ══════════════════════════════════════════════════════════════════════════════
#  GUI  –  WEBSITES VIEWER
# ══════════════════════════════════════════════════════════════════════════════
def gui_show_websites(parent):
    top = ctk.CTkToplevel(parent)
    top.title("🌐 Universal VRChat Websites")
    top.geometry("750x540")
    top.configure(fg_color="#0d0d1a")
    top.attributes("-topmost", True)

    txt = ctk.CTkTextbox(top, font=("Consolas", 12),
                          fg_color="#0a0a15", text_color="#00ff88")
    txt.pack(fill="both", expand=True, padx=12, pady=12)

    def _fetch():
        try:
            r = requests.get(WEBSITES_URL, timeout=10)
            content = re.sub(r'\033\[\d+m', '', r.text) if r.ok else "Error fetching."
        except Exception as e:
            content = f"Error: {e}"
        top.after(0, lambda: (txt.configure(state="normal"),
                               txt.delete("1.0", "end"),
                               txt.insert("end", content),
                               txt.configure(state="disabled")))
    threading.Thread(target=_fetch, daemon=True).start()

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN GUI CLASS
# ══════════════════════════════════════════════════════════════════════════════
ctk.set_appearance_mode(SETTINGS.get("theme", "dark"))
ctk.set_default_color_theme("dark-blue")

class VRCSTGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"VRCST v{VERSION}  –  VRC Tool by Kawaii Studio")
        w = SETTINGS.get("window_width",  1100)
        h = SETTINGS.get("window_height", 800)
        self.geometry(f"{w}x{h}")
        self.minsize(920, 700)
        self.configure(fg_color="#0a0a1a")
        try:
            self.iconbitmap("icon.ico")
        except Exception:
            pass

        # State
        self.auth_api    = None
        self.auth_cookie : str | None = None
        self.user_agent  = USER_AGENT
        self.bg_original = None
        self.bg_photo    = None
        self.logo_pil    = None
        self._bg_event   = threading.Event()
        self._logo_event = threading.Event()
        self._logged_user: dict | None = None

        self._build_ui()
        self.bind("<Configure>", self._on_resize)
        self.after(100, self._check_initial_login)

    # ── UI structure ───────────────────────────────────────────────────────
    def _build_ui(self):
        # Background canvas
        self.canvas = tk.Canvas(self, highlightthickness=0, bg="#0a0a1a")
        self.canvas.pack(fill="both", expand=True)

        self.main_container = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.main_container.place(relx=0, rely=0, relwidth=1, relheight=1)

        self._build_header()
        self._build_quick_toolbar()

        self.main_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=22, pady=(8, 4))

        self._build_console()

        # Load assets asynchronously
        threading.Thread(target=self._load_bg,   daemon=True).start()
        threading.Thread(target=self._load_logo, daemon=True).start()
        self.after(100, self._poll_bg)
        self.after(100, self._poll_logo)

    def _build_header(self):
        hdr = ctk.CTkFrame(self.main_container, corner_radius=0,
                            fg_color="#16213e", height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Left: logo + title
        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.pack(side="left", padx=14, pady=8)

        self.logo_label = ctk.CTkLabel(left, text="", width=42, height=42)
        self.logo_label.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(left, text=f"VRCST  v{VERSION}",
                     font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
                     text_color=SETTINGS.get("accent_color","#e94560")
                     ).pack(side="left")

        # Right: controls
        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.pack(side="right", padx=14, pady=8)

        self.status_label = ctk.CTkLabel(right, text="● Not logged in",
                                          text_color="#ff6b6b",
                                          font=ctk.CTkFont(size=11))
        self.status_label.pack(side="right", padx=(12, 0))

        for text, url, color in [
            ("VRChat",   VRCHAT_GROUP, "#2CC985"),
            ("Telegram", TELEGRAM_URL, "#0088cc"),
            ("Discord",  DISCORD_URL,  "#5865F2"),
        ]:
            ctk.CTkButton(right, text=text, width=72, height=28,
                          corner_radius=8, fg_color=color,
                          hover_color=self._dim(color),
                          font=ctk.CTkFont(size=11, weight="bold"),
                          command=lambda u=url: wb.open(u)).pack(side="right", padx=2)

        # Settings gear
        ctk.CTkButton(right, text="⚙", width=36, height=28,
                      corner_radius=8, fg_color="#252540", hover_color="#353560",
                      font=ctk.CTkFont(size=16),
                      command=self._open_settings).pack(side="right", padx=(0,6))

    def _build_quick_toolbar(self):
        """Row of quick-action icon buttons."""
        tb = ctk.CTkFrame(self.main_container, fg_color="#0e0e22", height=40,
                           corner_radius=0)
        tb.pack(fill="x")
        tb.pack_propagate(False)

        actions = [
            ("🔎 Lookup",     self._open_lookup),
            ("💾 Local DB",   self._open_localdb),
            ("📝 Notes",      self._open_notes),
            ("🎛 OSC",        self._open_osc),
            ("🌐 Websites",   lambda: gui_show_websites(self)),
            ("🔄 Refresh",    self._refresh_session),
            ("🚪 Logout",     self._logout),
        ]
        for label, cmd in actions:
            ctk.CTkButton(tb, text=label, height=30, width=95,
                          fg_color="transparent", hover_color="#252540",
                          text_color="#aaaacc",
                          font=ctk.CTkFont(size=11),
                          corner_radius=0,
                          command=cmd).pack(side="left", padx=1)

    def _build_console(self):
        if not SETTINGS.get("console_visible", True):
            return
        cf = ctk.CTkFrame(self.main_container, fg_color="#0f0f23", corner_radius=12)
        cf.pack(fill="x", padx=18, pady=(0, 12))
        ctk.CTkLabel(cf, text="📋 Console",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#777799").pack(anchor="w", padx=10, pady=(6,0))
        h = SETTINGS.get("console_height", 100)
        self.console_text = ctk.CTkTextbox(cf, height=h,
                                            font=("Consolas", 10),
                                            fg_color="#0a0a15",
                                            text_color="#00ff88",
                                            corner_radius=8)
        self.console_text.pack(fill="x", padx=10, pady=(4, 8))
        self.console_text.configure(state="disabled")
        sys.stdout = self._Redirector(self.console_text, self)
        sys.stderr = self._Redirector(self.console_text, self)

    # ── Background / logo loading ──────────────────────────────────────────
    def _load_bg(self):
        img = load_image_from_url(BANNER_URL)
        if img:
            try:
                img = ImageEnhance.Brightness(img).enhance(0.35)
            except Exception:
                pass
            self.bg_original = img
            self._bg_event.set()

    def _load_logo(self):
        img = load_image_from_url(LOGO_URL, size=(44, 44), crop_to_fit=True)
        if img:
            self.logo_pil = img
            self._logo_event.set()

    def _poll_bg(self):
        if self._bg_event.is_set():
            self._update_bg()
        else:
            self.after(150, self._poll_bg)

    def _poll_logo(self):
        if self._logo_event.is_set():
            if self.logo_pil:
                cimg = ctk.CTkImage(light_image=self.logo_pil,
                                    dark_image=self.logo_pil, size=(44, 44))
                self.logo_label.configure(image=cimg)
        else:
            self.after(150, self._poll_logo)

    def _update_bg(self):
        if not self.bg_original:
            return
        try:
            w, h = self.winfo_width(), self.winfo_height()
            if w < 2 or h < 2:
                return
            img    = self.bg_original.copy()
            ratio  = max(w / img.width, h / img.height)
            nw, nh = int(img.width*ratio), int(img.height*ratio)
            img    = img.resize((nw, nh), Image.Resampling.LANCZOS)
            l = (nw - w) // 2; t = (nh - h) // 2
            img    = img.crop((l, t, l+w, t+h))
            self.bg_photo = ImageTk.PhotoImage(img)
            self.canvas.delete("bg")
            self.canvas.create_image(0, 0, image=self.bg_photo, anchor="nw", tags="bg")
            self.canvas.lower("bg")
        except Exception:
            pass

    def _on_resize(self, event):
        if event.widget == self and self.bg_original:
            self.after(60, self._update_bg)

    # ── Login flow ────────────────────────────────────────────────────────
    def _check_initial_login(self):
        if os.path.exists(AUTH_PATH):
            try:
                cfg = Configuration(host=f"{BASE_API}")
                with ApiClient(cfg) as client:
                    client.user_agent = USER_AGENT
                    load_auth_cookie(client, AUTH_PATH)
                    api = authentication_api.AuthenticationApi(client)
                    user = api.get_current_user()
                    if getattr(user, "current_avatar_asset_url", None) is None:
                        user.current_avatar_asset_url = ""
                    self.auth_api    = api
                    save_auth_cookie(client, AUTH_PATH)
                    try:
                        self.auth_cookie = \
                            client.rest_client.cookie_jar._cookies["api.vrchat.cloud"]["/"]["auth"].value
                    except Exception:
                        self.auth_cookie = get_auth_cookie()
                    self.after(0, lambda: self._post_login(user.display_name))
                    return
            except Exception:
                try: os.remove(AUTH_PATH)
                except Exception: pass
        self._show_login()

    def _show_login(self, error: str = ""):
        for w in self.main_frame.winfo_children():
            w.destroy()

        box = ctk.CTkFrame(self.main_frame, fg_color="#1a1a2e", corner_radius=20)
        box.pack(expand=True, padx=60, pady=30)

        ctk.CTkLabel(box, text="🔐  VRChat Login",
                     font=ctk.CTkFont(size=26, weight="bold"),
                     text_color="#e94560").pack(pady=(28, 6), padx=60)

        self._err_lbl = ctk.CTkLabel(box, text=error or "",
                                      text_color="#ff6b6b",
                                      font=ctk.CTkFont(size=12))
        self._err_lbl.pack(pady=(0, 8))

        self._u_entry = ctk.CTkEntry(box, placeholder_text="Username / Email",
                                      width=280, height=40, corner_radius=10)
        self._u_entry.pack(pady=8)
        self._p_entry = ctk.CTkEntry(box, placeholder_text="Password",
                                      show="*", width=280, height=40,
                                      corner_radius=10)
        self._p_entry.pack(pady=8)
        self._p_entry.bind("<Return>", lambda _: self._do_login())

        self._login_btn = ctk.CTkButton(box, text="Login",
                                         command=self._do_login,
                                         width=280, height=44, corner_radius=10,
                                         fg_color="#2CC985", hover_color="#1fa36a",
                                         font=ctk.CTkFont(size=14, weight="bold"))
        self._login_btn.pack(pady=(12, 28))

    def _do_login(self):
        u = self._u_entry.get().strip()
        p = self._p_entry.get()
        if not u or not p:
            self._set_err("Please enter username and password.")
            return
        self._login_btn.configure(state="disabled", text="Logging in…")
        threading.Thread(target=self._login_thread, args=(u, p), daemon=True).start()

    def _login_thread(self, username: str, password: str):
        try:
            cfg = Configuration(username=username, password=password,
                                 host=f"{BASE_API}")
            with ApiClient(cfg) as client:
                client.user_agent = USER_AGENT
                api  = authentication_api.AuthenticationApi(client)
                try:
                    user = api.get_current_user()
                except ApiException as ex:
                    s = str(ex)
                    if "Email 2 Factor" in s:
                        self.after(0, lambda: self._login_btn.configure(
                            state="normal", text="Login"))
                        dlg  = ctk.CTkInputDialog(text="Enter Email 2FA Code:",
                                                   title="2FA Required")
                        code = dlg.get_input()
                        if code:
                            api.verify2_fa_email_code(
                                two_factor_email_code=TwoFactorEmailCode(code))
                            user = api.get_current_user()
                        else:
                            return
                    elif "2 Factor" in s:
                        self.after(0, lambda: self._login_btn.configure(
                            state="normal", text="Login"))
                        dlg  = ctk.CTkInputDialog(text="Enter 2FA Code:",
                                                   title="2FA Required")
                        code = dlg.get_input()
                        if code:
                            api.verify2_fa(two_factor_auth_code=TwoFactorAuthCode(code))
                            user = api.get_current_user()
                        else:
                            return
                    elif "401" in s or "Invalid" in s:
                        self.after(0, lambda: self._set_err("Invalid username or password."))
                        self.after(0, lambda: self._login_btn.configure(
                            state="normal", text="Login"))
                        return
                    else:
                        self.after(0, lambda: self._set_err("Login failed – try again."))
                        self.after(0, lambda: self._login_btn.configure(
                            state="normal", text="Login"))
                        return

                if getattr(user, "current_avatar_asset_url", None) is None:
                    user.current_avatar_asset_url = ""
                self.auth_api = api
                save_auth_cookie(client, AUTH_PATH)
                try:
                    self.auth_cookie = \
                        client.rest_client.cookie_jar._cookies["api.vrchat.cloud"]["/"]["auth"].value
                except Exception:
                    self.auth_cookie = get_auth_cookie()
                name = user.display_name
                self.after(0, lambda: self._post_login(name))

        except requests.exceptions.ConnectionError:
            self.after(0, lambda: self._set_err("No internet connection."))
            self.after(0, lambda: self._login_btn.configure(
                state="normal", text="Login"))
        except Exception as e:
            log.error(f"Login error: {e}")
            self.after(0, lambda: self._set_err("Connection error – try again."))
            self.after(0, lambda: self._login_btn.configure(
                state="normal", text="Login"))

    def _post_login(self, display_name: str):
        self.status_label.configure(
            text=f"● {display_name}", text_color="#2CC985")
        print(f"✅ Logged in as: {display_name}")

        if SETTINGS.get("auto_save_friends", False) and self.auth_api and self.auth_cookie:
            threading.Thread(target=save_friends_list,
                             args=(self.auth_api, self.auth_cookie),
                             daemon=True).start()
        self._show_main_menu()

    def _set_err(self, msg: str):
        if hasattr(self, "_err_lbl"):
            self._err_lbl.configure(text=f"⚠ {msg}")

    # ── Main menu ──────────────────────────────────────────────────────────
    def _show_main_menu(self):
        for w in self.main_frame.winfo_children():
            w.destroy()

        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=1)

        BUTTONS = [
            # (label, command, colour)
            ("🔍 Universal Avatar Search",   launch_networkdb_manager,    "#34495e"),
            ("🎭 Force Clone an Avatar",      self._gui_force_clone,        "#e74c3c"),
            ("📨 Invite Myself to Instance",  self._gui_invite_myself,      "#9b59b6"),
            ("📝 Start The Logger",           launch_loggerscript,          "#1abc9c"),
            ("👥 Auto Friendlist Request",    launch_friendlistrecovery,    "#2ecc71"),
            ("📨 Auto Invite Group",          autoinvitegroup,              "#f1c40f"),
            ("🌍 Create Custom Instance",     self._gui_create_custom,      "#3498db"),
            ("📦 Launch Asset Ripper",        run_asset_ripper,             "#e67e22"),
            ("🔍 Group ID Logger",            launch_group_id_logger,       "#9b59b6"),
            ("👤 User / Avatar / World Lookup",self._open_lookup,           "#16a085"),
            ("💾 Local DB Stats",             self._open_localdb,           "#8e44ad"),
            ("🎛 OSC Controls",               self._open_osc,               "#2c3e50"),
        ]

        row = col = 0
        for label, cmd, color in BUTTONS:
            btn = ctk.CTkButton(
                self.main_frame, text=label, command=cmd,
                height=62, corner_radius=12,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color=color,
                hover_color=self._dim(color),
                border_width=2,
                border_color=self._brighten(color),
            )
            btn.grid(row=row, column=col, padx=9, pady=8, sticky="ew")
            col += 1
            if col > 1:
                col = 0
                row += 1

    # ── Feature wrappers ──────────────────────────────────────────────────
    def _gui_force_clone(self):
        d = ctk.CTkInputDialog(text="Enter Avatar ID (avtr_…):", title="Force Clone")
        aid = d.get_input()
        if aid:
            threading.Thread(target=select_avatar, args=(aid, self.auth_cookie),
                             daemon=True).start()

    def _gui_invite_myself(self):
        d = ctk.CTkInputDialog(text="Enter VRChat instance URL:", title="Invite Myself")
        url = d.get_input()
        if url:
            wid, iid = extract_world_and_instance_id(url)
            if wid and iid:
                threading.Thread(
                    target=invitemyselftocustuminstance,
                    args=(self.auth_cookie, wid, iid), daemon=True).start()
            else:
                print("[ERROR] Could not parse World/Instance ID from URL.")

    def _gui_create_custom(self):
        d1 = ctk.CTkInputDialog(text="Enter World ID (wrld_…):", title="Custom Instance")
        wid = d1.get_input()
        if not wid: return
        d2 = ctk.CTkInputDialog(text="Instance name (max 16 chars):", title="Custom Instance")
        iname = d2.get_input()
        if not iname or len(iname) > 16:
            print("[ERROR] Instance name must be 1-16 characters.")
            return
        url = f"https://vrchat.com/home/launch?worldId={wid}&instanceId={iname}"
        print(f"Generated URL: {url}")
        threading.Thread(
            target=invitemyselftocustuminstance,
            args=(self.auth_cookie, wid, iname), daemon=True).start()

    # ── Quick toolbar actions ─────────────────────────────────────────────
    def _open_lookup(self, prefill: str = ""):
        LookupWindow(self, cookie=self.auth_cookie, prefill=prefill)

    def _open_localdb(self):
        LocalDBWindow(self)

    def _open_notes(self):
        NotesWindow(self)

    def _open_osc(self):
        OSCPanel(self)

    def _open_settings(self):
        SettingsWindow(self, on_save_callback=self._apply_settings)

    def _apply_settings(self):
        ctk.set_appearance_mode(SETTINGS.get("theme", "dark"))
        print("[Settings] Applied.")

    def _refresh_session(self):
        self._check_initial_login()

    def _logout(self):
        try:
            os.remove(AUTH_PATH)
        except Exception:
            pass
        self.auth_api    = None
        self.auth_cookie = None
        self.status_label.configure(text="● Not logged in", text_color="#ff6b6b")
        self._show_login()
        print("Logged out.")

    # ── Colour helpers ─────────────────────────────────────────────────────
    @staticmethod
    def _dim(hex_color: str, factor: float = 0.72) -> str:
        hex_color = hex_color.lstrip("#")
        r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return "#{:02x}{:02x}{:02x}".format(
            max(0, int(r*factor)), max(0, int(g*factor)), max(0, int(b*factor)))

    @staticmethod
    def _brighten(hex_color: str, factor: float = 1.25) -> str:
        hex_color = hex_color.lstrip("#")
        r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return "#{:02x}{:02x}{:02x}".format(
            min(255, int(r*factor)), min(255, int(g*factor)), min(255, int(b*factor)))

    # ── stdout redirector ─────────────────────────────────────────────────
    class _Redirector:
        def __init__(self, widget, root):
            self._w = widget
            self._r = root
        def write(self, s: str):
            try:
                self._r.after(0, lambda: self._write(s))
            except Exception:
                pass
        def _write(self, s: str):
            try:
                self._w.configure(state="normal")
                self._w.insert("end", s)
                self._w.see("end")
                self._w.configure(state="disabled")
            except Exception:
                pass
        def flush(self):
            pass

# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    try:
        check_for_updates()

        if SETTINGS.get("discord_rpc", True):
            threading.Thread(target=update_rich_presence, daemon=True).start()

        app = VRCSTGUI()
        app.mainloop()

    except Exception:
        err = traceback.format_exc()
        log.critical(f"CRASH: {err}")
        print("═══ CRASH ═══")
        print(err)
        input("Press Enter to exit…")
