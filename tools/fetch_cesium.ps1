# CalcEclipses Cesium 获取脚本（Windows PowerShell）
# 与 tools/fetch_cesium.sh 等价：npm pack cesium@1.120 → Build/Cesium → lib/cesium
# 由 run.bat 在 lib\cesium 缺失时自动调用；也可手动执行：
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\fetch_cesium.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$dest = Join-Path $root 'lib\cesium'
$ver  = '1.120'

if (Test-Path (Join-Path $dest 'Cesium.js')) {
    Write-Host "[fetch] lib\cesium 已存在，跳过"
    exit 0
}

# npm 可用性
try { $tgz = (& npm pack "cesium@$ver" --silent | Select-Object -Last 1).Trim() }
catch {
    Write-Host "[fetch] 需要 npm（Node.js）来获取 Cesium：https://nodejs.org/" -ForegroundColor Red
    exit 1
}
if (-not $tgz -or -not (Test-Path $tgz)) {
    Write-Host "[fetch] npm pack 未产出安装包" -ForegroundColor Red
    exit 1
}

Write-Host "[fetch] 解压 $tgz ..."
$tmp = Join-Path $env:TEMP ("cesium_fetch_" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp | Out-Null
tar -xzf $tgz -C $tmp
if ($LASTEXITCODE -ne 0) { Write-Host "[fetch] 解压失败" -ForegroundColor Red; exit 1 }

New-Item -ItemType Directory -Path (Join-Path $root 'lib') -Force | Out-Null
if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
Move-Item (Join-Path $tmp "package\Build\Cesium") $dest
Remove-Item -Recurse -Force $tmp
Remove-Item -Force $tgz

Write-Host "[fetch] 完成：lib\cesium"
Get-ChildItem $dest | Select-Object -ExpandProperty Name
