import os
import sys
import ctypes
import subprocess
import re
from typing import Dict, Optional, Tuple

class QosManager:
    """
    Manages Windows Network QoS (Quality of Service) policies to limit bandwidth
    for specific applications (e.g., chrome.exe, setup.exe, steam.exe).
    """

    POLICY_PREFIX = "NetLimit_"

    @staticmethod
    def is_admin() -> bool:
        """Check if the current process is running with Administrator privileges."""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    @staticmethod
    def restart_as_admin():
        """Restart the current application with elevated Administrator privileges."""
        script = os.path.abspath(sys.argv[0])
        params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}" {params}', None, 1
        )
        sys.exit(0)

    @classmethod
    def policy_name_for(cls, app_name: str) -> str:
        # Clean app name to create a valid Windows QoS policy name
        clean_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', app_name)
        return f"{cls.POLICY_PREFIX}{clean_name}"

    @classmethod
    def set_limit(cls, app_name: str, speed_bytes_per_sec: int) -> Tuple[bool, str]:
        """
        Apply a bandwidth limit in bytes/sec for a given application (e.g., 'chrome.exe').
        Windows NetQosPolicy expects BitsPerSecond.
        """
        bits_per_sec = int(speed_bytes_per_sec * 8)
        # Minimum supported by Windows QoS policy is 8000 bps (1 KB/s)
        if bits_per_sec < 8000:
            bits_per_sec = 8000

        policy_name = cls.policy_name_for(app_name)
        exe_pattern = app_name if app_name.lower().endswith(".exe") else f"{app_name}.exe"

        ps_cmd = (
            f"$existing = Get-NetQosPolicy -Name '{policy_name}' -ErrorAction SilentlyContinue; "
            f"if ($existing) {{ "
            f"  Set-NetQosPolicy -Name '{policy_name}' -ThrottleRateActionBitsPerSecond {bits_per_sec} -NetworkProfile All; "
            f"}} else {{ "
            f"  New-NetQosPolicy -Name '{policy_name}' -AppPathNameMatchCondition '{exe_pattern}' "
            f"  -ThrottleRateActionBitsPerSecond {bits_per_sec} -NetworkProfile All; "
            f"}}"
        )

        return cls._execute_ps(ps_cmd, elevate_if_needed=True)

    @classmethod
    def remove_limit(cls, app_name: str) -> Tuple[bool, str]:
        """Remove a previously applied bandwidth limit for an application."""
        policy_name = cls.policy_name_for(app_name)
        ps_cmd = f"Remove-NetQosPolicy -Name '{policy_name}' -Confirm:$false -ErrorAction SilentlyContinue"
        return cls._execute_ps(ps_cmd, elevate_if_needed=True)

    @classmethod
    def remove_all_limits(cls) -> Tuple[bool, str]:
        """Remove all active NetLimit policies."""
        ps_cmd = f"Get-NetQosPolicy -Name '{cls.POLICY_PREFIX}*' -ErrorAction SilentlyContinue | Remove-NetQosPolicy -Confirm:$false -ErrorAction SilentlyContinue"
        return cls._execute_ps(ps_cmd, elevate_if_needed=True)

    @classmethod
    def get_active_limits(cls) -> Dict[str, int]:
        """
        Returns a dictionary of active limits: {app_name: bytes_per_sec}.
        """
        ps_cmd = (
            f"Get-NetQosPolicy -Name '{cls.POLICY_PREFIX}*' -ErrorAction SilentlyContinue | "
            f"ForEach-Object {{ [PSCustomObject]@{{ Name = $_.Name; App = $_.AppPathNameMatchCondition; Throttle = $_.ThrottleRateActionBitsPerSecond }} }} | "
            f"ConvertTo-Csv -NoTypeInformation"
        )

        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=4
            )
            limits = {}
            if res.returncode == 0 and res.stdout:
                lines = [line.strip().strip('"') for line in res.stdout.splitlines() if line.strip()]
                # Skip CSV header
                for line in lines[1:]:
                    parts = [p.strip().strip('"') for p in line.split(',')]
                    if len(parts) >= 3:
                        name, app, throttle_bps = parts[0], parts[1], parts[2]
                        try:
                            bps = int(throttle_bps)
                            app_clean = app if app else name.replace(cls.POLICY_PREFIX, "")
                            limits[app_clean.lower()] = bps // 8
                        except ValueError:
                            pass
            return limits
        except Exception:
            return {}

    @classmethod
    def _execute_ps(cls, ps_cmd: str, elevate_if_needed: bool = True) -> Tuple[bool, str]:
        """
        Executes a PowerShell command. If admin, runs directly; if not, triggers UAC elevation.
        """
        if cls.is_admin():
            try:
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                    capture_output=True,
                    text=True,
                    timeout=6
                )
                if res.returncode == 0:
                    return True, "Başarıyla uygulandı."
                else:
                    return False, res.stderr.strip() or "Bilinmeyen bir hata oluştu."
            except Exception as e:
                return False, str(e)
        elif elevate_if_needed:
            # Launch via PowerShell with RunAs (UAC elevation prompt)
            encoded_cmd = ps_cmd.replace('"', '\\"')
            launch_script = (
                f"Start-Process powershell -Verb RunAs -WindowStyle Hidden "
                f"-ArgumentList '-NoProfile', '-NonInteractive', '-Command', \"{encoded_cmd}\""
            )
            try:
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", launch_script],
                    capture_output=True,
                    text=True,
                    timeout=8
                )
                if res.returncode == 0:
                    return True, "Yönetici onayı ile işlem gönderildi."
                return False, res.stderr.strip()
            except Exception as e:
                return False, str(e)
        else:
            return False, "Yönetici yetkisi gereklidir."

