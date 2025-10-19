$body = @{
    episode_id = "newsroom-2024-bb580"
    target_stage = "discovered"
    force_reprocess = $false
} | ConvertTo-Json

Write-Host "Testing episode processing..."
Write-Host "Episode ID: newsroom-2024-bb580"
Write-Host "Body: $body"
Write-Host ""

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/episodes/process" `
        -Method POST `
        -ContentType "application/json" `
        -Body $body
    
    Write-Host "Status: $($response.StatusCode)"
    Write-Host "Response:"
    $response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error: $_"
    if ($_.Exception.Response) {
        $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response Body: $responseBody"
    }
}
