#!/usr/bin/env python3
"""打包 GitHub Release 完整包（源码 + 本地 Cesium + 第三方许可），幂等。

设计要点：
  - 源码文件复用 git 的跟踪/未跟踪未忽略清单（自动排除 tmp/、lib/cesium/、
    .workbuddy/、*.bak、*.log 等），无需维护第二份排除表；
  - 再单独注入 lib/cesium/（本地构建产物，被 .gitignore 排除但随包分发，
    这样下载者免 npm、离线可用）；
  - 在包内 lib/cesium/LICENSE.md 放 Cesium Apache-2.0 原文，满足随代码分发许可的要求；
  - 版本号格式 vX.Y.Z；同名包重复运行直接覆盖（幂等）。

用法：
    python3 tools/pack_release.py v1.0.0
    python3 tools/pack_release.py              # 未给版本时尝试从 git tag 读取

产物：
    tmp/release/CalcEclipses-vX.Y.Z.zip   （tmp/ 不入库）
"""
import os
import re
import sys
import zipfile
import hashlib
import shutil
import subprocess
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CESIUM_LICENSE_SRC = os.path.join(ROOT, "docs", "licenses", "Cesium-1.120-LICENSE.md")
CESIUM_DIR = os.path.join(ROOT, "lib", "cesium")
OUT_DIR = os.path.join(ROOT, "tmp", "release")
VER_RE = re.compile(r"^v\d+\.\d+\.\d+$")


def git_files():
    """已跟踪 + 未跟踪未忽略文件（等价于「若现在 git add -A 会纳入的文件」）。"""
    out = set()
    for args in (["git", "ls-files", "-z"],
                 ["git", "ls-files", "-z", "--others", "--exclude-standard"]):
        r = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        out.update(p.decode("utf-8", "replace") for p in r.stdout.split(b"\0") if p)
    return sorted(p for p in out if not p.endswith("/"))


def resolve_version(argv):
    if argv:
        v = argv[0]
    else:
        r = subprocess.run(["git", "describe", "--tags", "--exact-match", "HEAD"],
                           cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        v = r.stdout.decode().strip()
    if not VER_RE.match(v or ""):
        sys.exit(f"版本号需为 vX.Y.Z（如 v1.0.0），收到：{v!r}\n"
                 "用法：python3 tools/pack_release.py v1.0.0")
    return v


def main():
    version = resolve_version(sys.argv[1:])
    if not os.path.isfile(os.path.join(CESIUM_DIR, "Cesium.js")):
        sys.exit("缺少 lib/cesium/Cesium.js，请先运行 tools/fetch_cesium.sh（或 .ps1）")
    if not os.path.isfile(CESIUM_LICENSE_SRC):
        sys.exit(f"缺少第三方许可文件：{CESIUM_LICENSE_SRC}")

    top = f"CalcEclipses-{version}"
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"CalcEclipses-{version}.zip")
    if os.path.exists(out_path):
        os.remove(out_path)  # 幂等：覆盖同名包

    files = git_files()
    # 注入本地 Cesium（被 gitignore，需手工遍历）
    for base, _dirs, names in os.walk(CESIUM_DIR):
        for n in names:
            rel = os.path.relpath(os.path.join(base, n), ROOT)
            files.append(rel.replace(os.sep, "/"))
    files = sorted(set(files))

    added = []
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for rel in files:
            src = os.path.join(ROOT, rel)
            if not os.path.isfile(src):
                continue
            zi = zipfile.ZipInfo(f"{top}/{rel}", date_time=datetime.now().timetuple()[:6])
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            if rel.endswith(".sh"):
                zi.external_attr = 0o755 << 16  # 一键脚本保留可执行位
            with open(src, "rb") as f:
                z.writestr(zi, f.read())
            added.append(rel)

        # 第三方许可：随 Cesium 代码一起分发（Apache-2.0 要求随代码附带许可原文）
        with open(CESIUM_LICENSE_SRC, "rb") as f:
            z.writestr(f"{top}/lib/cesium/LICENSE.md", f.read())
        added.append("lib/cesium/LICENSE.md (第三方许可注入)")

        # 包内说明
        note = (f"CalcEclipses {version}\n"
                f"打包时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"包含：全部源码 + 本地 Cesium 1.120（Build 产物）+ 第三方许可\n"
                f"运行：解压后 Linux/macOS 执行 ./run.sh，Windows 双击 run.bat；\n"
                f"      因 Cesium 已随包提供，启动脚本会跳过 npm 下载，可离线使用。\n"
                f"许可：本项目 MIT（见 LICENSE）；CesiumJS Apache-2.0（见 lib/cesium/LICENSE.md）。\n")
        z.writestr(f"{top}/RELEASE.txt", note.encode("utf-8"))

    sha = hashlib.sha256()
    with open(out_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            sha.update(chunk)
    size_mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"完成：{out_path}")
    print(f"文件数：{len(added)}　包体：{size_mb:.1f} MB")
    print(f"SHA256：{sha.hexdigest()}")


if __name__ == "__main__":
    main()
