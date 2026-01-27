# Export Monitor - Git Workflow Script
# This script follows Semantic Versioning 2.0.0 (https://semver.org/)
# Automates: create branch, commit, push, create PR (or direct to main), tag release

param(
    [string]$Message = "",
    [string]$BranchName = "",
    [switch]$SkipSync,
    [switch]$SkipCommit,
    [switch]$DirectToMain,
    [switch]$TagRelease,
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
}Syncing with remote..." -ForegroundColor Cyan
    git fetch --all --tags --prune
    
    $currentBranch = git branch --show-current
    $remote = git rev-parse '@{u}' 2>$null
    
    if ($LASTEXITCODE -eq 0) {
        $local = git rev-parse HEAD
        if ($local -ne $remote) {
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
                Write-Error "Branches diverged. Resolve manually."
                exit 1
            }
        } else {
            Write-Host "Already up to date" -ForegroundColor Green
        }
    } else {
        Write-Host "No tracking branch (new branch)" -ForegroundColor Yellow
    }
}

function New-FeatureBranch {
    param([string]$Message)
    
    # Ensure we're on main and up to date
    $currentBranch = git branch --show-current
    if ($currentBranch -ne "main") {
        Write-Host "Switching to main branch..." -ForegroundColor Cyan
        git checkout main
    }
    
    Sync-GitRepository
    
    # Generate branch name from message or version
    $version = Get-ManifestVersion
    $branchName = $BranchName
    
    if ([string]::IsNullOrWhiteSpace($branchName)) {
        if ([string]::IsNullOrWhiteSpace($Message)) {
            $branchName = "feature/v$version"
        } else {
            # Create branch name from message
            $sanitized = $Message -replace '[^a-zA-Z0-9\s-]', '' -replace '\s+', '-'
            $branchName = "feature/$sanitized".ToLower().Substring(0, [Math]::Min(50, "feature/$sanitized".Length))
        }
    }
    
    # Check if branch exists
    $existingBranch = git branch --list $branchName
    if ($existingBranch) {
        Write-Host "Branch $branchName already exists, checking out..." -ForegroundColor Yellow
        git checkout $branchName
    } else {
        Write-Host "Creating new branch: $branchName" -ForegroundColor Green
        git checkout -b $branchName
    }
    
    return $branchName   }
    } else {
        Write-Host "Already up to date" -ForegroundColor Green
    }
}

function Invoke-GitCommit {
    param([string]$CommitMessage)
    if (Test-GitClean) {
        Write-Host "No changes to commit" -ForegroundColor Green
        return $false
    param([string]$Branch)
    
    Write-Host "Pushing to remote..." -ForegroundColor Cyan
    
    # Push branch (set upstream if new)
    git push -u origin $Branch
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Push failed"
        exit 1
    }
    
    Write-Host "Pushed successfully" -ForegroundColor Green
}

function Push-GitTags {
    Write-Host "Pushing tags to remote..." -ForegroundColor Cyan
    git push --tags
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Push tags failed"
        exit 1
    }
    Write-Host "Tags pushed successfully" -ForegroundColor Green
}

function Show-PullRequestInfo {
    param([string]$Branch, [string]$Message)
    
    # Get GitHub repo URL
    $remoteUrl = git remote get-url origin
    $repoUrl = $remoteUrl -replace '\.git$', '' -replace 'git@github.com:', 'https://github.com/'
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Next Steps: Create Pull Request" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Branch pushed: $Branch" -ForegroundColor Green
    Write-Host ""
    Write-Host "Create PR using GitHub CLI:" -ForegroundColor Yellow
    Write-Host "  gh pr create --title `"$Message`" --body `"$Message`" --base main --head $Branch" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Or create PR on GitHub:" -ForegroundColor Yellow
    Write-Host "  $repoUrl/compare/$Branch" -ForegroundColor Gray
    Write-Host ""
    Write-Host "After PR is merged, run this to tag the release:" -ForegroundColor Yellow
    Write-Host "  .\sync-and-tag.ps1 -TagRelease" -ForegroundColor Gray
    Write-Host ""
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
    if (($existingTag -or $remoteTag) -and -not $F==" -ForegroundColor Cyan
Write-Host "Export Monitor - Git Workflow (SemVer)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Mode 1: Tag a release (after PR merged)
if ($TagRelease) {
    Write-Host "Tag Release Mode" -ForegroundColor Cyan
    Write-Host ""
    
    # Ensure we're on main
    $currentBranch = git branch --show-current
    if ($currentBranch -ne "main") {
        Write-Host "Switching to main branch..." -ForegroundColor Cyan
        git checkout main
    }
    
    Sync-GitRepository
    Write-Host ""
    
    $version = Get-ManifestVersion
    Write-Host "Manifest version: $version" -ForegroundColor Green
    
    if (-not (Test-SemVerFormat -Version $version)) {
        Write-Error "Invalid SemVer: $version"
        exit 1
    }
    
    $tagCreated = New-GitTag -Version $version
    Write-Host ""
    
    if ($tagCreated) {
        Push-GitTags
        Write-Host ""
        Write-Host "Release v$version tagged and published!" -ForegroundColor Green
    } else {
        Write-Host "Tag already exists" -ForegroundColor Yellow
    }
    
    if (-not $SkipSync) {
        Sync-ToHomeAssistant
    }
    
    exit 0
}

# Mode 2: Direct to main (old workflow, use with caution)
if ($DirectToMain) {
    Write-Host "Direct to Main Mode (bypassing PR workflow)" -ForegroundColor Yellow
    Write-Host ""
    
    $currentBranch = git branch --show-current
    if ($currentBranch -ne "main") {
        Write-Host "Switching to main branch..." -ForegroundColor Cyan
        git checkout main
    }
    
    Sync-GitRepository
    Write-Host ""
    
    if (-not $SkipCommit) {
        $committed = Invoke-GitCommit -CommitMessage $Message
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
        Push-GitChanges -Branch "main"
        Push-GitTags
        Write-Host ""
        Write-Host "Published to main with tag v$version" -ForegroundColor Green
    }
    
    if (-not $SkipSync) {
        Sync-ToHomeAssistant
    }
    
    exit 0
}

# Mode 3: Feature branch workflow (default, recommended)
Write-Host "Feature Branch Workflow (Recommended)" -ForegroundColor Green
Write-Host ""

$version = Get-ManifestVersion
Write-Host "Target version: $version" -ForegroundColor Green

if (-not (Test-SemVerFormat -Version $version)) {
    Write-Error "Invalid SemVer in manifest.json: $version"
    exit 1
}
Write-Host ""

# Create/checkout feature branch
$branch = New-FeatureBranch -Message $Message
Write-Host ""

# Commit changes
if (-not $SkipCommit) {
    $committed = Invoke-GitCommit -CommitMessage $Message
    Write-Host ""
    
    if (-not $committed) {
        Write-Host "No changes to commit. Branch ready for additional work." -ForegroundColor Yellow
        exit 0
    }
} else {
    Write-Host "Skipping commit step" -ForegroundColor Yellow
    Write-Host ""
}

# Push branch
Push-GitChanges -Branch $branch
Write-Host ""

# Show PR creation instructions
Show-PullRequestInfo -Branch $branch -Message $Message

if (-not $SkipSync) {
    Write-Host "Syncing to HA for testing..." -ForegroundColor Cyan
    Sync-ToHomeAssistant
}

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
