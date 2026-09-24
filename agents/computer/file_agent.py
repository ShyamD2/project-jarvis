"""
J.A.R.V.I.S. File Management Agent (Computer Pillar).
Handles file and directory operations, path aliases, zip archives, search, and safe deletion.
"""

import os
import shutil
import zipfile
import subprocess
import glob
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisFileAgent")

import tempfile

class SecurityViolationError(PermissionError):
    """Raised when an operation attempts to access or modify paths outside the allowed sandbox jail."""
    pass

USER_HOME = os.path.expanduser("~")
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

ALLOWED_JAIL_ROOTS = [
    PROJECT_ROOT,
    os.path.join(USER_HOME, "Desktop"),
    os.path.join(USER_HOME, "Downloads"),
    os.path.join(USER_HOME, "Documents"),
    os.path.join(USER_HOME, "Pictures"),
    tempfile.gettempdir()
]

FORBIDDEN_PATHS = [
    os.environ.get("SystemRoot", r"C:\Windows"),
    os.environ.get("ProgramFiles", r"C:\Program Files"),
    os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    r"C:\Recovery",
    r"C:\System Volume Information",
    os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32"),
]

PATH_ALIASES = {
    "desktop": os.path.join(USER_HOME, "Desktop"),
    "downloads": os.path.join(USER_HOME, "Downloads"),
    "documents": os.path.join(USER_HOME, "Documents"),
    "workspace": PROJECT_ROOT,
    "jarvis": PROJECT_ROOT,
    "pictures": os.path.join(USER_HOME, "Pictures")
}


class FileAgent:
    def __init__(self):
        pass

    def _check_jail(self, target_path: str, operation: str = "write") -> Tuple[bool, str]:
        """
        Validates that target_path resolves strictly within allowed jail directories
        and does not touch forbidden system paths.
        """
        real_path = os.path.realpath(os.path.abspath(target_path))
        
        # 1. Reject forbidden roots immediately
        for fb in FORBIDDEN_PATHS:
            if not fb:
                continue
            fb_real = os.path.realpath(os.path.abspath(fb))
            try:
                if os.path.splitdrive(real_path)[0].lower() == os.path.splitdrive(fb_real)[0].lower():
                    if os.path.commonpath([real_path, fb_real]).lower() == fb_real.lower():
                        msg = f"SecurityViolation: Path '{real_path}' belongs to protected system directory '{fb_real}'"
                        logger.critical(f"[FileAgent] {msg} for operation '{operation}'")
                        return False, msg
            except ValueError:
                pass

        # 2. Check if inside at least one allowed jail root
        for jail in ALLOWED_JAIL_ROOTS:
            jail_real = os.path.realpath(os.path.abspath(jail))
            try:
                if os.path.splitdrive(real_path)[0].lower() == os.path.splitdrive(jail_real)[0].lower():
                    if os.path.commonpath([real_path, jail_real]).lower() == jail_real.lower():
                        return True, "Allowed"
            except ValueError:
                continue

        msg = f"SecurityViolation: Path '{real_path}' is outside permitted sandbox roots for operation '{operation}'"
        logger.critical(f"[FileAgent] {msg}")
        return False, msg

    def _resolve_path(self, path_str: str) -> str:
        """Resolves shortcuts/aliases to absolute paths"""
        p = path_str.strip().strip('"').strip("'")
        p_lower = p.lower()
        for alias, actual in PATH_ALIASES.items():
            if p_lower == alias:
                return actual
            if p_lower.startswith(f"{alias}/") or p_lower.startswith(f"{alias}\\"):
                return os.path.join(actual, p[len(alias) + 1:])
        return os.path.abspath(os.path.expandvars(os.path.expanduser(p)))

    def open_path(self, target_path: str) -> Dict[str, Any]:
        """Opens file, folder, or application associated with the file type"""
        real_path = self._resolve_path(target_path)
        logger.info(f"[FileAgent] Opening path: {real_path}")
        if not os.path.exists(real_path):
            return {"success": False, "error": f"Path not found: {real_path}"}
        try:
            os.startfile(real_path)
            return {"success": True, "action": "open", "path": real_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_folder(self, folder_path: str) -> Dict[str, Any]:
        """Creates a directory and any intermediate folders"""
        real_path = self._resolve_path(folder_path)
        safe, err = self._check_jail(real_path, "create_folder")
        if not safe:
            return {"success": False, "error": err}
        logger.info(f"[FileAgent] Creating folder: {real_path}")
        try:
            os.makedirs(real_path, exist_ok=True)
            return {"success": True, "path": real_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_file(self, file_path: str, content: str = "") -> Dict[str, Any]:
        """Creates or writes a file with optional content"""
        real_path = self._resolve_path(file_path)
        safe, err = self._check_jail(real_path, "create_file")
        if not safe:
            return {"success": False, "error": err}
        logger.info(f"[FileAgent] Creating file: {real_path}")
        try:
            os.makedirs(os.path.dirname(real_path), exist_ok=True)
            with open(real_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"success": True, "path": real_path, "bytes": len(content.encode("utf-8"))}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def rename_item(self, source: str, new_name: str) -> Dict[str, Any]:
        """Renames a file or folder"""
        src = self._resolve_path(source)
        if not os.path.exists(src):
            return {"success": False, "error": f"Source not found: {src}"}
        dest = os.path.join(os.path.dirname(src), new_name)
        safe_src, err_src = self._check_jail(src, "rename_item_source")
        if not safe_src:
            return {"success": False, "error": err_src}
        safe_dest, err_dest = self._check_jail(dest, "rename_item_dest")
        if not safe_dest:
            return {"success": False, "error": err_dest}
        try:
            os.rename(src, dest)
            return {"success": True, "old_path": src, "new_path": dest}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def move_item(self, source: str, destination: str) -> Dict[str, Any]:
        """Moves a file or folder to a target destination"""
        src = self._resolve_path(source)
        dest = self._resolve_path(destination)
        safe_src, err_src = self._check_jail(src, "move_item_source")
        if not safe_src:
            return {"success": False, "error": err_src}
        safe_dest, err_dest = self._check_jail(dest, "move_item_dest")
        if not safe_dest:
            return {"success": False, "error": err_dest}
        try:
            shutil.move(src, dest)
            return {"success": True, "source": src, "destination": dest}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def copy_item(self, source: str, destination: str) -> Dict[str, Any]:
        """Copies a file or folder"""
        src = self._resolve_path(source)
        dest = self._resolve_path(destination)
        safe_dest, err_dest = self._check_jail(dest, "copy_item_dest")
        if not safe_dest:
            return {"success": False, "error": err_dest}
        try:
            if os.path.isdir(src):
                shutil.copytree(src, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dest)
            return {"success": True, "source": src, "destination": dest}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_item(self, target_path: str, permanent: bool = False) -> Dict[str, Any]:
        """
        Deletes a file or directory.
        By default, sends to the Windows Recycle Bin (Safe delete, Tier 2).
        If permanent=True, permanently removes (Tier 3 Destructive).
        """
        real_path = self._resolve_path(target_path)
        safe, err = self._check_jail(real_path, "delete_item")
        if not safe:
            return {"success": False, "error": err}
        if not os.path.exists(real_path):
            return {"success": False, "error": f"Path not found: {real_path}"}

        logger.info(f"[FileAgent] Deleting: {real_path} (permanent={permanent})")
        if permanent:
            try:
                if os.path.isdir(real_path):
                    shutil.rmtree(real_path)
                else:
                    os.remove(real_path)
                return {"success": True, "action": "permanent_delete", "path": real_path}
            except Exception as e:
                return {"success": False, "error": str(e)}

        # Safe delete via Windows Shell Recycle Bin
        try:
            safe_path = real_path.replace("'", "''")
            is_dir = os.path.isdir(real_path)
            method = "DeleteDirectory" if is_dir else "DeleteFile"
            ps_cmd = f"""
            Add-Type -AssemblyName Microsoft.VisualBasic
            [Microsoft.VisualBasic.FileIO.FileSystem]::{method}('{safe_path}', 'OnlyErrorDialogs', 'SendToRecycleBin')
            """
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
            if res.returncode == 0:
                return {"success": True, "action": "recycle_bin", "path": real_path}
            # Fallback to standard remove if Shell COM fails
            if is_dir:
                shutil.rmtree(real_path)
            else:
                os.remove(real_path)
            return {"success": True, "action": "deleted", "path": real_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def empty_recycle_bin(self) -> Dict[str, Any]:
        """Empties the Windows Recycle Bin"""
        logger.warning("[FileAgent] Emptying Windows Recycle Bin")
        try:
            res = subprocess.run(["powershell", "-NoProfile", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"], capture_output=True)
            return {"success": True, "action": "recycle_bin_emptied"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def search_files(self, pattern: str, directory: str = "workspace", max_results: int = 20) -> Dict[str, Any]:
        """Searches for files matching pattern within a directory"""
        root_dir = self._resolve_path(directory)
        logger.info(f"[FileAgent] Searching for '{pattern}' in {root_dir}")
        matches = []
        try:
            for root, _, files in os.walk(root_dir):
                for f in files:
                    if pattern.lower() in f.lower():
                        matches.append(os.path.join(root, f))
                        if len(matches) >= max_results:
                            break
                if len(matches) >= max_results:
                    break
            return {"success": True, "pattern": pattern, "matches": matches, "count": len(matches)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def zip_archive(self, source_path: str, zip_output_path: Optional[str] = None) -> Dict[str, Any]:
        """Compresses a file or directory into a ZIP archive"""
        src = self._resolve_path(source_path)
        if not os.path.exists(src):
            return {"success": False, "error": f"Source not found: {src}"}

        out_zip = self._resolve_path(zip_output_path) if zip_output_path else f"{src}.zip"
        safe, err = self._check_jail(out_zip, "zip_archive_destination")
        if not safe:
            return {"success": False, "error": err}

        try:
            with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED) as z:
                if os.path.isfile(src):
                    z.write(src, os.path.basename(src))
                else:
                    for root, _, files in os.walk(src):
                        for f in files:
                            full_p = os.path.join(root, f)
                            rel_p = os.path.relpath(full_p, src)
                            z.write(full_p, rel_p)
            return {"success": True, "archive_path": out_zip}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def extract_zip(self, zip_path: str, extract_to: Optional[str] = None) -> Dict[str, Any]:
        """Extracts a ZIP archive"""
        src = self._resolve_path(zip_path)
        if not os.path.exists(src):
            return {"success": False, "error": f"Archive not found: {src}"}
        out_dir = self._resolve_path(extract_to) if extract_to else os.path.splitext(src)[0]
        safe, err = self._check_jail(out_dir, "extract_zip_destination")
        if not safe:
            return {"success": False, "error": err}
        try:
            os.makedirs(out_dir, exist_ok=True)
            with zipfile.ZipFile(src, 'r') as z:
                z.extractall(out_dir)
            return {"success": True, "extracted_to": out_dir}
        except Exception as e:
            return {"success": False, "error": str(e)}


file_agent = FileAgent()
