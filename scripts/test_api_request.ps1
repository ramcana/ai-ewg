$body = @{
    episode_id = "test-episode"
    target_stage = "discovered"
    force_reprocess = $false
} | ConvertTo-Json

Write-Host "Testing API endpoint..."
Write-Host "Body: $body"

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/episodes/process" `
        -Method POST `
        -ContentType "application/json" `
        -Body $body
    
    Write-Host "Status: $($response.StatusCode)"
    Write-Host "Response: $($response.Content)"
} catch {
    Write-Host "Error: $_"
    Write-Host "Status Code: $($_.Exception.Response.StatusCode.Value__)"
    Write-Host "Response: $($_.Exception.Response | ConvertTo-Json)"
}
