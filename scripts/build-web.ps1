$ErrorActionPreference = "Stop"

Push-Location "$PSScriptRoot\..\client"
try {
  & "C:\src\flutter\bin\flutter.bat" build web --release

  $bootstrap = Join-Path (Get-Location) "build\web\flutter_bootstrap.js"
  if (Test-Path $bootstrap) {
    $content = Get-Content -LiteralPath $bootstrap -Raw
    $content = $content -replace 'serviceWorkerSettings:\s*\{\s*serviceWorkerVersion:\s*"[^"]+"\s*/\* Flutter''s service worker is deprecated and will be removed in a future Flutter release\. \*/\s*\}', 'serviceWorkerSettings: null'
    $content = $content -replace '"mainJsPath":"main\.dart\.js"', '"mainJsPath":"main.dart.js?v=vaeagent-20260707-1"'
    Set-Content -LiteralPath $bootstrap -Value $content -Encoding UTF8
  }

  $serviceWorker = Join-Path (Get-Location) "build\web\flutter_service_worker.js"
  if (Test-Path $serviceWorker) {
    Remove-Item -LiteralPath $serviceWorker -Force
  }
}
finally {
  Pop-Location
}
