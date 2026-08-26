#!/usr/bin/env python3
"""Tool registry for SmashDeck."""
from __future__ import annotations

import os
import subprocess
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.paths import LOGS_TOOLS, PROJECT_ROOT, ensure_data_dirs, tool_log_path

ensure_data_dirs()

try:
    from utils import process_manager as pm
except Exception:
    pm = None


class BaseTool(ABC):
    name: str = "base"
    category: str = "general"
    description: str = ""
    default_timeout: int = 120

    def __init__(self, **kwargs):
        self.options = kwargs

    @abstractmethod
    def get_cmd(self) -> List[str]:
        raise NotImplementedError

    def parse(self, stdout: str, stderr: str) -> Dict[str, Any]:
        return {"raw_head": (stdout or stderr)[:800], "lines": len((stdout or "").splitlines())}

    def run(self, timeout: Optional[int] = None) -> Dict[str, Any]:
        cmd = self.get_cmd()
        timeout = timeout or self.default_timeout
        log_path = str(tool_log_path(f"tool_{self.name}"))
        env = os.environ.copy()
        venv_bin = PROJECT_ROOT / ".venv" / "bin"
        if venv_bin.exists():
            env["PATH"] = f"{venv_bin}:{env.get('PATH', '')}"
        try:
            with open(log_path, "w") as lf:
                lf.write(f"# SmashDeck {self.name}\n# CMD: {' '.join(cmd)}\n\n")
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, start_new_session=True
            )
            stdout, _ = proc.communicate(timeout=timeout)
            with open(log_path, "a") as lf:
                lf.write(stdout or "")
            parsed = self.parse(stdout or "", "")
            return {
                "tool": self.name, "cmd": cmd, "rc": proc.returncode,
                "stdout": (stdout or "")[:2000], "parsed": parsed,
                "log_path": log_path, "success": proc.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
            return {"tool": self.name, "rc": 124, "error": "timeout", "log_path": log_path}
        except Exception as e:
            return {"tool": self.name, "rc": -1, "error": str(e), "log_path": log_path}

    def launch(self, key: Optional[str] = None, target: Optional[str] = None) -> Optional[str]:
        if pm is None:
            return None
        key = key or f"{self.name}_{int(time.time())}"
        cmd = self.get_cmd()
        log_path = str(LOGS_TOOLS / f"{key}.log")
        pid = pm.start(cmd, key=key, log_path=log_path)
        return key if pid else None


class NmapTool(BaseTool):
    name = "nmap"
    category = "recon"
    description = "Host/port discovery"

    def get_cmd(self) -> List[str]:
        target = self.options.get("target", "127.0.0.1")
        ports = self.options.get("ports", "1-1024")
        return ["nmap", "-sV", "-sC", "-p", ports, "-oX", "-", target]

    def parse(self, stdout: str, stderr: str) -> Dict[str, Any]:
        return {
            "summary": f"nmap: open mentions={stdout.lower().count('open')}",
            "raw_head": (stdout or "")[:600],
        }


class NucleiTool(BaseTool):
    name = "nuclei"
    category = "vuln"
    default_timeout = 300

    def get_cmd(self) -> List[str]:
        target = self.options.get("target", "http://127.0.0.1")
        return ["nuclei", "-u", target, "-jsonl", "-silent", "-rate-limit", "100"]

    def parse(self, stdout: str, stderr: str) -> Dict[str, Any]:
        lines = [l for l in (stdout or "").splitlines() if l.strip()]
        return {"summary": f"nuclei: {len(lines)} findings", "count": len(lines)}


class BlueSonarTool(BaseTool):
    name = "blue_sonar"
    category = "bluetooth"
    description = "Continuous BT RSSI track (l2ping + hcitool)"
    default_timeout = 3600

    def get_cmd(self) -> List[str]:
        target = self.options.get("target") or self.options.get("mac") or ""
        hci = self.options.get("hci") or "hci0"
        sleep = self.options.get("sleep", 1)
        script = PROJECT_ROOT / "third_party" / "blue_sonar" / "blue_sonar"
        if script.is_file():
            return ["sudo", "-n", str(script), "--target", str(target), "--interface", str(hci), "--sleep", str(sleep)]
        return ["python3", "-m", "utils.blue_sonar", "-t", str(target), "-i", str(hci), "-s", str(sleep), "--duration", "60"]

    def launch(self, key: Optional[str] = None, target: Optional[str] = None) -> Optional[str]:
        mac = target or self.options.get("target") or self.options.get("mac")
        hci = self.options.get("hci") or "hci0"
        if not mac:
            return None
        try:
            from utils import blue_sonar as bs
            st = bs.start(str(mac), hci=str(hci), sleep=float(self.options.get("sleep", 1)))
            if st.get("mac"):
                return f"blue_sonar_{st['mac'].replace(':', '')}"
        except Exception:
            pass
        return super().launch(key=key, target=target)


TOOL_REGISTRY: Dict[str, type] = {
    "nmap": NmapTool,
    "nuclei": NucleiTool,
    "blue_sonar": BlueSonarTool,
}


def get_tool(name: str, **opts) -> BaseTool:
    cls = TOOL_REGISTRY.get(name)
    if not cls:
        raise ValueError(f"Unknown tool: {name}. Available: {list(TOOL_REGISTRY)}")
    return cls(**opts)


if __name__ == "__main__":
    print("Registry:", list(TOOL_REGISTRY))
    print(get_tool("nmap", target="127.0.0.1").get_cmd())
