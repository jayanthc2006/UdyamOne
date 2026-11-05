$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

Add-Type -AssemblyName System.Runtime.WindowsRuntime

$asyncMethods = [System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object {
        $_.Name -eq "AsTask" -and
        $_.IsGenericMethodDefinition -and
        $_.GetParameters().Length -eq 1
    }
$asTaskMethod = $asyncMethods |
    Where-Object {
        $_.GetGenericArguments().Length -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -like "IAsyncOperation*"
    } |
    Select-Object -First 1

function Wait-WinRtOperation($operation, [Type] $resultType) {
    $task = $asTaskMethod.MakeGenericMethod($resultType).Invoke(
        $null,
        @($operation)
    )
    $task.Wait()
    return $task.Result
}

$storageFileType = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$streamType = [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage, ContentType=WindowsRuntime]
$decoderType = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$bitmapType = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$ocrResultType = [Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType=WindowsRuntime]
$engine = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]::TryCreateFromUserProfileLanguages()

$paths = [Console]::In.ReadToEnd() | ConvertFrom-Json
if ($null -eq $engine) {
    [PSCustomObject]@{ engine_available = $false; results = @() } |
        ConvertTo-Json -Compress -Depth 4
    exit 0
}

$results = foreach ($path in $paths) {
    try {
        $file = Wait-WinRtOperation (
            $storageFileType::GetFileFromPathAsync([string]$path)
        ) $storageFileType
        $stream = Wait-WinRtOperation (
            $file.OpenAsync(
                [Windows.Storage.FileAccessMode, Windows.Storage, ContentType=WindowsRuntime]::Read
            )
        ) $streamType
        try {
            $decoder = Wait-WinRtOperation (
                $decoderType::CreateAsync($stream)
            ) $decoderType
            $bitmap = Wait-WinRtOperation (
                $decoder.GetSoftwareBitmapAsync()
            ) $bitmapType
            $ocr = Wait-WinRtOperation (
                $engine.RecognizeAsync($bitmap)
            ) $ocrResultType
            $text = [string]$ocr.Text
            [PSCustomObject]@{
                status = if ([string]::IsNullOrWhiteSpace($text)) { "UNREADABLE" } else { "SUCCEEDED" }
                text = $text
                confidence = $null
            }
        } finally {
            $stream.Dispose()
        }
    } catch {
        [PSCustomObject]@{
            status = "FAILED"
            text = ""
            confidence = $null
        }
    }
}

[PSCustomObject]@{
    engine_available = $true
    results = @($results)
} | ConvertTo-Json -Compress -Depth 4
