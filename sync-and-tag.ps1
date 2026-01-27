# Export Monitor - Git Workflow Script
# This script follows Semantic Versioning 2.0.0 (https://semver.org/)
# Automates: git pull, commit, tag, push, optional HA sync

param(
    [string]$Message = "",
    [switch]$SkipSync,
    [switch]$SkipCommit,
    [switch]$Force
)

function Get-ManifestVersion {
    $manifestPath = ".\custom_components\export_monitor\manifest.json"
    if (Test-Path $manifestPath) {
        $manifest = Get-Content $manifestPath | ConvertFrom-Json
        return $manifest.version
    }
    Write-Error "manifest.json not found!"
    exit 1
}

function Test-GitClean {
    $status = git status --porcelain
    return [string]::IsNullOrWhiteSpace($status)
}

function Test-SemVerFormat {
    param([string]$Version)
    return $Version -match '^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$'
}

function Sync-GitRepository {
    Write-Host "Pulling latest changes from remote..." -ForegroundColor Cyan
    git fetch --all --tags --prune
    $local = git rev-parse HEAD
    $remote = git rev-parse '@{u}' 2>$null
    if ($LASTEXITCODE -eq 0 -and $local -ne $remote) {
        $base = git merge-base HEAD '@{u}'
        if ($local -eq $base) {
            Write-Host "Behind remote, pulling changes..." -ForegroundColor Yellow
            git pull --rebase
            if ($LASTEXITCODE -ne 0) {
                Write-Error "Pull failed."
                exit 1
            }
        } elseif ($remote -eq $base) {
            Write-Host "Local ahead of remote" -ForegroundColor Green
        } else {
            Write-Error "Branches diverged."
            exit 1
        }
    } else {
        Write-Host "Already up to date" -ForegroundColor Green
    }
}

function Invoke-GitCommit {
    param([string]$CommitMessage)
    if (Test-GitClean) {
        Write-Host "No changes to commit" -ForegroundColor Green
        return $false
    }
    Write-Host "Changes detected:" -ForegroundColor Yellow
    git status --short
    Write-Host ""
    if ([string]::IsNullOrWhiteSpace($CommitMessage)) {
        Write-Host "Enter commit message:" -ForegroundColor Cyan
        $CommitMessage = Read-Host "Message"
    }
    if ([string]::IsNullOrWhiteSpace($CommitMessage)) {
        Write-Error "Commit message required"
        exit 1
    }
    Write-Host "Committing changes..." -ForegroundColor Green
    git add .
    git commit -m $CommitMessage
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Commit failed"
        exit 1
    }
    return $true
}

function New-GitTag {
    param([string]$Version)
    if (-not (Test-SemVerFormat -Version $Version)) {
        Write-Error "Invalid SemVer: $Version"
        exit 1
    }
    $tagName = "v$Version"
    $existingTag = git tag -l $tagName
    $remoteTag = git ls-remote --tags origin $tagName 2>$null
    if (($existingTag -or $remoteTag) -and -not $Force) {
        Write-Host "Tag $tagName exists" -ForegroundColor Yellow
        return $false
    }
    if (($existingTag -or $remoteTag) -and $Force) {
        Write-Host "Deleting existing tag $tagName..." -ForegroundColor Yellow
        git tag -d $tagName 2>$null
        git push origin :refs/tags/$tagName 2>$null
    }
    Write-Host "Creating tag $tagName..." -ForegroundColor Green
    git tag -a $tagName -m "Release version $Version"
    return $true
}

function Push-GitChanges {
    Write-Host "Pushing to remote..." -ForegroundColor Cyan
    git push
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Push failed"
        exit 1
    }
    git push --tags
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Push tags failed"
        exit 1
    }
    Write-Host "Pushed successfully" -ForegroundColor Green
}

function Sync-ToHomeAssistant {
    param([string]$RemoteHost = "192.168.0.202")
    Write-Host "Syncing to HA at $RemoteHost..." -ForegroundColor Cyan
    Write-Host "Sync method not configured. Edit script to enable SSH or SMB sync." -ForegroundColor Yellow
}

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Export Monitor - Git Workflow (SemVer)" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

Sync-GitRepository
Write-Host ""

if (-not $SkipCommit) {
    $committed = Invoke-GitCommit -CommitMessage $Message
    Write-Host ""
} else {
    Write-Host "Skipping commit step" -ForegroundColor Yellow
    Write-Host ""
}

$version = Get-ManifestVersion
Write-Host "Manifest version: $version" -ForegroundColor Green

if (-not (Test-SemVerFormat -Version $version)) {
    Write-Error "Invalid SemVer: $version"
    exit 1
}

$tagCreated = New-GitTag -Version $version
Write-Host ""

if ($tagCreated -or $committed) {
    Push-GitChanges
    Write-Host ""
} else {
    Write-Host "Nothing to push" -ForegroundColor Yellow
    Write-Host ""
}

if (-not $SkipSync) {
    Sync-ToHomeAssistant
} else {
    Write-Host "Skipping HA sync" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done! Version $version is published." -ForegroundColor Green
Write-Host ""
Write-Host "SemVer Guide:" -ForegroundColor Cyan
Write-Host "  MAJOR (X.0.0) - Breaking changes" -ForegroundColor Gray
Write-Host "  MINOR (0.X.0) - New features, backward compatible" -ForegroundColor Gray
Write-Host "  PATCH (0.0.X) - Bug fixes, backward compatible" -ForegroundColor Gray
