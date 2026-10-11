"""只读查询 Windows 凭据管理器里是否有 GitHub 凭据。

用途：确认 Git Credential Manager 的 OAuth 授权是否真的把令牌存下来了。
只读取凭据的「目标名称」列表，不读取、不打印任何密钥内容。

用法：python check_git_credential.py
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

CRED_TYPE_GENERIC = 1
CRED_ENUM_ALL = 0


class CREDENTIAL_ATTRIBUTE(ctypes.Structure):
    _fields_ = [
        ("Keyword", wintypes.LPWSTR),
        ("Flags", wintypes.DWORD),
        ("ValueSize", wintypes.DWORD),
        ("Value", ctypes.POINTER(ctypes.c_byte)),
    ]


class CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.POINTER(CREDENTIAL_ATTRIBUTE)),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


PCREDENTIAL = ctypes.POINTER(CREDENTIAL)


def main() -> int:
    try:
        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    except OSError as exc:
        print(f"[FAIL] 无法加载 advapi32：{exc}")
        return 1

    advapi.CredEnumerateW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(ctypes.POINTER(PCREDENTIAL)),
    ]
    advapi.CredEnumerateW.restype = wintypes.BOOL
    advapi.CredFree.argtypes = [ctypes.c_void_p]

    count = wintypes.DWORD(0)
    credentials = ctypes.POINTER(PCREDENTIAL)()
    ok = advapi.CredEnumerateW(None, CRED_ENUM_ALL, ctypes.byref(count), ctypes.byref(credentials))
    if not ok:
        error = ctypes.get_last_error()
        print(f"[FAIL] CredEnumerateW 失败，Win32 错误码 {error}")
        return 1

    hits: list[str] = []
    try:
        for index in range(count.value):
            cred = credentials[index].contents
            target = cred.TargetName or ""
            user = cred.UserName or ""
            if "git" in target.lower() or "github" in target.lower():
                # 只报告目标名与用户名，绝不输出 CredentialBlob（那是密钥）
                hits.append(f"{target}  (用户: {user})")
    finally:
        advapi.CredFree(credentials)

    print(f"凭据管理器中共 {count.value} 条凭据")
    if hits:
        print("与 git / GitHub 相关的凭据：")
        for item in hits:
            print("  -", item)
        print("\n结论：Git Credential Manager 的授权已生效，凭据已保存。")
    else:
        print("未找到任何 git / GitHub 相关凭据。")
        print("结论：授权可能未完成，或凭据存在别的位置。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
