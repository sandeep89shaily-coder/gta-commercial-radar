$ErrorActionPreference = 'Stop'
try {
    $root = Split-Path -Parent $MyInvocation.MyCommand.Path
    $folder = Join-Path $root 'settings'
    $target = Join-Path $folder 'deepseek_key.dpapi'
    Write-Host 'DeepSeek API key setup (Windows account encrypted)'
    Write-Host 'Your key will not be shown, sent to GitHub, or stored as plain text.'
    $secret = Read-Host 'Paste your DeepSeek API key and press Enter' -AsSecureString
    if ($secret.Length -lt 10) { throw 'No valid-looking key entered; nothing was changed.' }
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
    $encrypted = ConvertFrom-SecureString -SecureString $secret
    $temp = $target + '.tmp'
    [System.IO.File]::WriteAllText($temp, $encrypted, [System.Text.Encoding]::ASCII)
    Move-Item -LiteralPath $temp -Destination $target -Force
    Write-Host 'SUCCESS: Encrypted API key saved for this Windows account.'
    Write-Host 'DeepSeek remains opt-in; saving the key does not make paid API calls.'
} catch {
    Write-Host ('SETUP FAILED: ' + $_.Exception.Message)
    exit 1
}
