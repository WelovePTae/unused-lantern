param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PlatformIOArguments
)

$projectDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectDirectory

# PlatformIO currently rejects Python 3.15 and Windows can hit MAX_PATH while
# unpacking ESP32 packages. uv provides Python 3.12 and this keeps its cache short.
$env:PLATFORMIO_CORE_DIR = Join-Path (Split-Path -Parent $projectDirectory) ".platformio"
$uvArguments = @(
    "run", "--python", "3.12", "--with", "platformio", "platformio"
) + $PlatformIOArguments

& uv @uvArguments
exit $LASTEXITCODE
