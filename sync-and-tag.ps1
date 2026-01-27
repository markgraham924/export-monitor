# Auto-sync to remote HA and create/push git tag based on manifest version
# Run this after making changes and committing

param(
    [string]$Message = "Update to v$(Get-ManifestVersion)"
)

function Get-ManifestVersion {
    $manifest = Get-Content "custom_components/export_monitor/manifest.json" | ConvertFrom-Json
    return $manifest.version
}

function Update-HA {
    # Sync to remote HA at 192.168.0.202 using SSH
    $version = Get-ManifestVersion
    Write-Host "Syncing to HA (192.168.0.202)..." -ForegroundColor Cyan
    
    # Using rsync via WSL or Git Bash - adjust if needed
    ssh -i $env:HA_SSH_KEY root@192.168.0.202 "docker exec homeassistant cp -r /config/custom_components/export_monitor /tmp/export_monitor_backup"
    rsync -avz --delete -e "ssh -i $env:HA_SSH_KEY" "custom_components/export_monitor/" "root@192.168.0.202:/config/custom_components/export_monitor/"
    ssh -i $env:HA_SSH_KEY root@192.168.0.202 "docker restart homeassistant"
    
    Write-Host "✓ Synced to HA and restarted" -ForegroundColor Green
}

function New-GitTag {
    $version = Get-ManifestVersion
    Write-Host "Creating tag v$version..." -ForegroundColor Cyan
    
    # Check if tag already exists
    $existing = git tag | Where-Object { $_ -eq $version }
    if ($existing) {
        Write-Host "Tag v$version already exists, skipping..." -ForegroundColor Yellow
        return
    }
    
    # Create and push tag
    git tag $version
    git push origin $version
    Write-Host "✓ Tagged and pushed v$version" -ForegroundColor Green
}

# Main
Write-Host "=" * 60
Write-Host "Export Monitor: Sync & Tag" -ForegroundColor Cyan
Write-Host "=" * 60

$version = Get-ManifestVersion
Write-Host "Current version: v$version" -ForegroundColor Yellow

# Commit check
$status = git status --porcelain
if ($status) {
    Write-Host "Uncommitted changes detected. Please commit first:" -ForegroundColor Yellow
    git status
    exit 1
}

# Tag
New-GitTag

# Optional: Sync to HA (set $env:HA_SSH_KEY first)
if ($env:HA_SSH_KEY) {
    $sync = Read-Host "Sync to HA? (y/n)"
    if ($sync -eq 'y') {
        Update-HA
    }
}

Write-Host "=" * 60
Write-Host "Done!" -ForegroundColor Green
Write-Host "=" * 60
