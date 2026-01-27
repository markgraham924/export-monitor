# Semantic Versioning Guide

This project follows [Semantic Versioning 2.0.0](https://semver.org/).

## Version Format: MAJOR.MINOR.PATCH

- **MAJOR** (X.0.0) - Incompatible API changes
- **MINOR** (0.X.0) - New backward-compatible functionality  
- **PATCH** (0.0.X) - Backward-compatible bug fixes

## When to Increment

### MAJOR Version (Breaking Changes)
Increment when making changes that break backward compatibility:

- **Configuration changes** that require users to reconfigure
- **Service signature changes** (parameters renamed, removed, or behavior changed)
- **Entity removal** or renaming
- **Minimum HA version increase** that drops support for older versions
- **Required entity changes** (new required sensors users must configure)

**Examples:**
- `1.2.3` → `2.0.0`: Renamed service from `start_discharge` to `discharge_start`
- `1.5.0` → `2.0.0`: Removed `cutoff_soc` parameter (now automatic)
- `2.1.4` → `3.0.0`: Changed entity IDs from `sensor.export_*` to `sensor.energy_export_*`

### MINOR Version (New Features)
Increment when adding backward-compatible functionality:

- **New optional parameters** to existing services
- **New entities** added (buttons, sensors, numbers)
- **New optional configuration** options
- **Deprecation warnings** (functionality still works)
- **New features** that don't affect existing behavior

**Examples:**
- `1.0.0` → `1.1.0`: Added reconfiguration support via device page
- `1.1.0` → `1.2.0`: Added new optional `duration` parameter to `start_discharge` service
- `1.2.0` → `1.3.0`: Added new sensor for battery SOC prediction

### PATCH Version (Bug Fixes)
Increment for backward-compatible bug fixes:

- **Bug fixes** that don't change public API
- **Internal code improvements** (refactoring, optimization)
- **Documentation updates**
- **Dependency updates** (if no API impact)
- **Error handling improvements**
- **Calculation corrections** that fix incorrect behavior

**Examples:**
- `1.0.0` → `1.0.1`: Fixed domain detection for `input_number` vs `number` entities
- `1.0.1` → `1.0.2`: Fixed crash when Solcast sensor unavailable
- `1.2.3` → `1.2.4`: Corrected energy calculation rounding error

## Workflow

We use a **feature branch + pull request** workflow for better release management and change tracking.

### Development Workflow (Recommended)

#### 1. Make Your Changes
Edit code, test locally on your HA instance at 192.168.0.202.

#### 2. Update Version in manifest.json
Based on the change type, update `custom_components/export_monitor/manifest.json`:

```json
{
  "version": "1.0.3"  // Increment appropriately
}
```

#### 3. Create Feature Branch and Push

**PowerShell (Windows):**
```powershell
.\sync-and-tag.ps1 -Message "Fix entity control bug"
```

The script will:
1. ✓ Create/checkout feature branch (e.g., `feature/fix-entity-control-bug`)
2. ✓ Commit your changes
3. ✓ Push branch to GitHub
4. ✓ Show instructions for creating PR

#### 4. Create Pull Request

**Using GitHub CLI:**
```powershell
gh pr create --title "Fix entity control bug" --body "Fixes #123" --base main --head feature/fix-entity-control-bug
```

**Using GitHub Web:**
Visit the link shown in script output, or go to GitHub → Pull Requests → New

#### 5. Review and Merge PR

Review the changes, ensure CI passes, then merge the PR on GitHub.

#### 6. Tag the Release

After PR is merged to main:

```powershell
.\sync-and-tag.ps1 -TagRelease
```

This will:
1. ✓ Switch to main branch
2. ✓ Pull latest changes
3. ✓ Create git tag from manifest version (e.g., `v1.0.3`)
4. ✓ Push tag to GitHub
5. ✓ Trigger GitHub Actions to create release

### Quick Workflow (Direct to Main)

For hotfixes or when working solo (use sparingly):

```powershell
.\sync-and-tag.ps1 -Message "Hotfix for critical bug" -DirectToMain
```

This bypasses the PR workflow and commits directly to main with a tag.

### After Release

HACS will automatically detect the new tag and offer it as an update to users.

## Common Scenarios

### Scenario 1: Bug Fix
You fixed entity control not working with `input_number` entities.

```json
// Before: "version": "1.0.0"
// After:  "version": "1.0.1"
```

Run: `.\sync-and-tag.ps1 -Message "Fix: Support input_number entity domain"`

### Scenario 2: New Feature
You added reconfiguration support via device page.

```json
// Before: "version": "1.0.1"
// After:  "version": "1.1.0"
```

Run: `.\sync-and-tag.ps1 -Message "Add entity reconfiguration support"`

### Scenario 3: Breaking Change
You changed service parameter from `cutoff_soc` to `duration` (incompatible).

```json
// Before: "version": "1.1.0"
// After:  "version": "2.0.0"
```

Run: `.\sync-and-tag.ps1 -Message "BREAKING: Replace cutoff_soc with duration parameter"`

## Version History

- **1.0.0** - Initial release with energy-based export control
- **1.0.1** - Fixed entity domain detection (input_number vs number)

## Validation

The automation scripts validate version format:
- ✓ Valid: `1.0.0`, `1.2.3`, `10.0.1`
- ✗ Invalid: `v1.0.0` (no 'v' prefix), `1.0` (must have patch), `01.0.0` (no leading zeros)

## References

- [Semantic Versioning Specification](https://semver.org/)
- [Home Assistant Integration Versioning](https://developers.home-assistant.io/docs/creating_integration_manifest/#version)
- [HACS Requirements](https://hacs.xyz/docs/publish/integration)
