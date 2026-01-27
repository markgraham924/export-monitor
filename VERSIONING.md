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

### 1. Make Your Changes
Edit code, test locally on your HA instance at 192.168.0.202.

### 2. Update Version in manifest.json
Based on the change type, update `custom_components/export_monitor/manifest.json`:

```json
{
  "version": "1.0.2"  // Increment appropriately
}
```

### 3. Run Automation Script

**PowerShell (Windows):**
```powershell
.\sync-and-tag.ps1 -Message "Fixed entity control bug"
```

**Bash (Linux/Mac):**
```bash
./tag.sh "Fixed entity control bug"
```

The script will:
1. ✓ Pull latest changes from GitHub
2. ✓ Commit your changes with provided message
3. ✓ Validate SemVer format
4. ✓ Create annotated git tag (e.g., `v1.0.2`)
5. ✓ Push commits and tags to GitHub
6. ✓ (Optional) Sync to Home Assistant instance

### 4. HACS Updates Automatically
Once pushed, HACS will detect the new tag and offer it as an update to users.

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
