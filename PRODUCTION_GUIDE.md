# Production Deployment Guide

This guide covers production deployment, monitoring, and troubleshooting for the Energy Export Monitor integration.

## ⚠️ Critical Safety Information

This integration controls battery discharge for solar energy systems. **Incorrect operation can result in:**
- Financial penalties from energy providers if export limits are exceeded
- Unexpected battery behavior
- Potential violation of grid connection terms and conditions

**Always monitor the system closely during initial deployment.**

---

## System Requirements

### Minimum Requirements
- Home Assistant 2024.1.0 or later
- Alpha ESS battery system with Hillview Lodge integration
- Solcast PV Forecast integration
- Stable network connection (integration polls every 10 seconds)

### Recommended Configuration
- UPS or battery backup for Home Assistant server
- Network redundancy for critical systems
- Automated backups of Home Assistant configuration
- Monitoring dashboard for system health

---

## Pre-Deployment Checklist

### 1. Verify Dependencies
- [ ] Alpha ESS integration installed and configured
- [ ] Solcast PV Forecast integration installed
- [ ] All helper entities created (discharge button, power, SOC, duration)
- [ ] Test manual discharge control through Alpha ESS integration

### 2. Validate Sensor Data
```yaml
# Check these sensors return valid numeric values:
- sensor.alphaess_battery_soc                 # Should be 0-100
- sensor.alphaess_today_s_energy_from_pv      # Should be positive kWh
- sensor.alphaess_today_s_energy_feed_to_grid_meter  # Should be positive kWh
- sensor.solcast_pv_forecast_forecast_today   # Should be positive kWh
```

### 3. Configure Safety Margins
```yaml
# Recommended conservative settings for initial deployment:
target_export: 0          # Most conservative: no export allowed
min_soc: 25               # Leave more reserve initially
safety_margin: 1.0        # Double the default 0.5 kWh
```

### 4. Test in Safe Mode
1. Set `enable_auto_discharge: false` initially
2. Manually trigger discharge using button
3. Monitor for 1-2 hours to verify calculations
4. Check exported energy stays within limits
5. Enable auto-discharge only after successful manual testing

---

## Monitoring & Health Checks

### Critical Sensors to Monitor

#### 1. System Health Sensor
`sensor.export_monitor_system_health`

**Expected States:**
- ✅ **Healthy**: All systems operational
- ⚠️ **Stale Data**: Sensor updates delayed (>30s)
- 🔴 **Error**: Critical error occurred
- 🔴 **Circuit Breaker Open**: Too many failures, system paused

**Action Required:**
- **Stale Data**: Check network connectivity, Home Assistant load
- **Error**: Check `sensor.export_monitor_error_state` for details
- **Circuit Breaker Open**: Fix underlying issue, wait 60s for reset

#### 2. Error State Sensor
`sensor.export_monitor_error_state`

**Possible Error States:**
| Error State | Meaning | Action Required |
|-------------|---------|-----------------|
| `none` | No errors | ✅ Normal operation |
| `soc_read_failed` | Cannot read battery SOC | Check `sensor.alphaess_battery_soc` entity |
| `stale_data` | Sensor data too old | Check coordinator update logs |
| `discharge_power_set_failed` | Cannot set discharge power | Check `number.alphaess_template_force_discharging_power` |
| `discharge_start_failed` | Cannot start discharge | Check `input_boolean.alphaess_helper_force_discharging` |
| `discharge_stop_failed` | Cannot stop discharge | **Critical**: Manually stop battery discharge |
| `no_data` | Coordinator has no data | Check all required sensors are available |

#### 3. Data Staleness Sensor
`sensor.export_monitor_data_staleness`

**Normal Range:** 0-15 seconds
**Warning:** 15-30 seconds
**Critical:** >30 seconds

If data staleness exceeds 30 seconds:
1. Check Home Assistant system load (CPU, memory)
2. Review coordinator logs for update failures
3. Verify sensor entities are responding
4. Consider increasing `DEFAULT_SCAN_INTERVAL` if system overloaded

#### 4. Circuit Breaker Status
`sensor.export_monitor_circuit_breaker_status`

**States:**
- `Closed`: Normal operation
- `Open`: System has paused due to repeated failures

**Attributes:**
- `failure_count`: Number of consecutive failures
- `last_failure_time`: When last failure occurred
- `can_attempt`: Whether new operations are allowed

**Reset Conditions:**
- Automatic: 60 seconds after last failure
- Manual: Restart Home Assistant
- Automatic: One successful update

---

## Persistent Notifications

The integration sends persistent notifications for critical failures:

### ⚠️ SOC Sensor Failed
**Cause:** Cannot read valid battery state of charge
**Impact:** Discharge cannot start (safety protection)
**Resolution:**
1. Check Alpha ESS integration is online
2. Verify `sensor.alphaess_battery_soc` entity exists
3. Check entity state is numeric (0-100)
4. Restart Alpha ESS integration if needed

### ⚠️ Stale Data Detected
**Cause:** Coordinator hasn't updated in >30 seconds
**Impact:** Discharge prevented to avoid outdated calculations
**Resolution:**
1. Check system load (Settings → System → System Health)
2. Review logs for coordinator update errors
3. Verify network connectivity to sensor sources
4. Check if any sensors are unavailable

### ⚠️ Discharge Power Set Failed
**Cause:** Cannot set discharge power on battery
**Impact:** Discharge aborted to prevent unpredictable behavior
**Resolution:**
1. Check `number.alphaess_template_force_discharging_power` is available
2. Verify Alpha ESS integration is responding
3. Check network connectivity to battery
4. Try manual discharge through Alpha ESS integration

### ⚠️ Discharge Start Failed
**Cause:** Cannot enable discharge button
**Impact:** Battery discharge did not start
**Resolution:**
1. Check `input_boolean.alphaess_helper_force_discharging` exists
2. Verify entity is not locked or disabled
3. Check Alpha ESS Modbus connection
4. Manually enable discharge to test connectivity

### 🔴 Discharge Stop Failed (CRITICAL)
**Cause:** Cannot disable discharge button
**Impact:** Battery may still be discharging
**Resolution:**
1. **IMMEDIATELY**: Check battery status manually
2. Stop discharge through Alpha ESS app/interface
3. Verify discharge has actually stopped
4. Check Modbus connection to battery
5. Do not rely on automation until fixed

---

## Failure Scenarios & Recovery

### Scenario 1: Sensor Becomes Unavailable During Discharge

**Symptoms:**
- Discharge continues despite missing sensor data
- Stale data sensor shows high age
- System health shows "Stale Data"

**Automatic Protection:**
- New discharge operations blocked
- Existing discharge continues (safer than abrupt stop)
- Circuit breaker opens after 5 consecutive failures

**Manual Intervention:**
1. Check which sensor is unavailable (review logs)
2. Fix sensor connectivity
3. Monitor discharge completion
4. Circuit breaker auto-resets after 60s

### Scenario 2: Network Timeout During Service Call

**Symptoms:**
- Error "Service call timeout" in logs
- Error state sensor shows failure
- Persistent notification sent

**Automatic Protection:**
- Service call aborted after 5 seconds
- Discharge operation not started
- Error state recorded

**Manual Intervention:**
1. Check Home Assistant load
2. Verify battery system is responding
3. Test manual service calls to battery
4. Retry operation after fixing issue

### Scenario 3: Invalid Sensor Values

**Symptoms:**
- Warning "value X outside range" in logs
- Sensor validation errors
- Operations may fail to start

**Examples of Invalid Values:**
- SOC > 100% or < 0%
- Negative PV production
- Grid export jumping by >10 kWh between reads

**Automatic Protection:**
- Invalid values rejected
- Sensor returns default/None
- Operation prevented with invalid data

**Manual Intervention:**
1. Check sensor hardware/integration
2. Review sensor history for anomalies
3. Recalibrate sensors if needed
4. Verify integration configuration

### Scenario 4: Circuit Breaker Opens

**Symptoms:**
- System health shows "Circuit Breaker Open"
- Circuit breaker status shows "Open"
- Warning "Circuit breaker is open" in logs
- All new operations blocked

**Automatic Protection:**
- After 5 consecutive failures, operations stop
- System pauses for 60 seconds
- Auto-resets after timeout

**Manual Intervention:**
1. Review error state sensor for root cause
2. Fix underlying issue
3. Wait 60s for automatic reset
4. Or restart Home Assistant to force reset
5. Monitor first operation after reset

### Scenario 5: Over-Export Despite Discharge

**Symptoms:**
- Export exceeds configured limit
- Safety margin insufficient
- Headroom calculation incorrect

**Possible Causes:**
- Solar forecast significantly wrong
- Background loads changed
- Sensor reporting delay
- Safety margin too small

**Immediate Actions:**
1. **Stop discharge immediately**
2. Check actual export vs limit
3. Review safety margin (increase to 1.0+ kWh)
4. Verify PV forecast accuracy
5. Check if other loads changed

**Prevention:**
- Use conservative safety margin (≥0.5 kWh)
- Monitor forecast accuracy
- Test calculations in low-risk periods
- Consider increasing margin during peak sun

---

## Logging & Diagnostics

### Enable Debug Logging

Add to `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.export_monitor: debug
    custom_components.export_monitor.coordinator: debug
    custom_components.export_monitor.error_handler: debug
```

### Key Log Messages

#### Normal Operation
```
INFO: Started discharge: 3.000 kW for 30.0 min (cutoff SOC: 20%, target: 1.500 kWh)
DEBUG: Calculated discharge duration: 30.0 minutes (headroom: 1.500 kWh, target: 3000 W)
INFO: Stopped discharge
```

#### Error Conditions
```
ERROR: Sensor sensor.alphaess_battery_soc value 150.0 outside valid range [0.0, 100.0]
ERROR: Service call timeout: number.set_value (timeout: 5.0s)
WARNING: Circuit breaker 'export_monitor_update' opened after 5 failures
ERROR: Cannot start discharge: coordinator data is stale (age: 35.2 seconds)
```

### Diagnostic Endpoints

Check coordinator state via Developer Tools → States:
```yaml
sensor.export_monitor_system_health:
  state: Healthy
  attributes:
    error_state: none
    data_age_seconds: 8.3
    circuit_breaker_failures: 0
    discharge_active: true

sensor.export_monitor_data_staleness:
  state: 8.3
  attributes:
    is_stale: false
    threshold_seconds: 30
```

---

## Disaster Recovery

### Emergency Stop Procedure

If you need to immediately stop all discharge operations:

1. **Via Home Assistant:**
   ```yaml
   service: export_monitor.stop_discharge
   ```

2. **Via Alpha ESS Integration:**
   - Disable `input_boolean.alphaess_helper_force_discharging`

3. **Via Alpha ESS App/Web Interface:**
   - Log into Alpha ESS monitoring
   - Manually stop force discharge

4. **Hardware Level:**
   - Access battery inverter display
   - Stop discharge through menu

### System Recovery After Failure

1. **Clear all error notifications:**
   ```yaml
   service: persistent_notification.dismiss
   data:
     notification_id: export_monitor_*
   ```

2. **Reset circuit breaker:**
   - Wait 60 seconds, or
   - Restart Home Assistant

3. **Verify sensor health:**
   - Check all required sensors are available
   - Verify values are in valid ranges
   - Test service calls manually

4. **Restart integration:**
   ```
   Settings → Devices & Services → Export Monitor → ⋮ → Reload
   ```

5. **Gradual restart:**
   - Test manual discharge first
   - Monitor for 1-2 hours
   - Enable auto-discharge after verification

### Backup Configuration

**Before Production:**
```yaml
# Take snapshot of Home Assistant
Settings → System → Backups → Create Backup

# Export configuration
Settings → Devices & Services → Export Monitor → ⋮ → Download Diagnostics
```

**Regular Maintenance:**
- Weekly automated backups
- Monthly configuration exports
- Test restore procedure quarterly

---

## Performance Tuning

### System Load Considerations

**Default scan interval:** 10 seconds

If system shows high load:
1. Increase scan interval in code (DEFAULT_SCAN_INTERVAL)
2. Disable CI planning if not needed
3. Disable charge planning if not needed
4. Monitor sensor.export_monitor_data_staleness

### Reducing False Alarms

**Adjust timeouts for slow systems:**

In `error_handler.py`:
```python
SERVICE_CALL_TIMEOUT = 10.0  # Increase from 5.0s
```

In `error_handler.py` StaleDataDetector:
```python
max_age_seconds=60  # Increase from 30s
```

### Network Resilience

For unstable networks:
1. Increase service call timeout
2. Increase stale data threshold
3. Increase circuit breaker threshold (from 5 to 10 failures)
4. Add retry logic (future enhancement)

---

## Security Considerations

### Access Control
- Limit access to Export Monitor configuration
- Use Home Assistant user authentication
- Consider separate user for battery control
- Audit service call logs regularly

### Data Validation
- All sensor values validated against ranges
- Service calls timeout after 5s
- State verification after critical operations
- Circuit breaker prevents abuse

### Fail-Safe Behavior
- Stale data blocks new discharges
- Invalid sensor values rejected
- Operations abort on first failure
- Manual override always available

---

## Compliance & Liability

### Grid Connection Compliance

**This integration helps you comply with grid connection terms, but:**
- You are responsible for verifying export limits
- Monitor actual exports regularly
- Set conservative safety margins
- Keep logs of discharge operations

### Liability Disclaimer

The integration provides tools and safeguards, but:
- User is responsible for correct configuration
- User must monitor system operation
- Developer not liable for financial penalties
- Use at your own risk

### Documentation Requirements

For grid operator compliance, document:
- Export limit (specified in grid connection agreement)
- Safety margin configured
- Discharge operation logs
- Any limit breaches and causes

---

## Support & Troubleshooting

### Before Requesting Support

1. **Check system health sensors:**
   - sensor.export_monitor_system_health
   - sensor.export_monitor_error_state
   - sensor.export_monitor_data_staleness
   - sensor.export_monitor_circuit_breaker_status

2. **Review logs:**
   - Enable debug logging
   - Check last 100 lines for errors
   - Note error patterns

3. **Verify configuration:**
   - All sensors available
   - Values in valid ranges
   - Network connectivity stable

4. **Test manually:**
   - Try manual discharge
   - Verify service calls work
   - Check Alpha ESS integration

### Reporting Issues

Include in issue report:
1. System health sensor states
2. Error messages from logs
3. Configuration (redact sensitive data)
4. Steps to reproduce
5. Expected vs actual behavior

### Community Support

- **Issues**: [GitHub Issues](https://github.com/markgraham924/export-monitor/issues)
- **Discussions**: [GitHub Discussions](https://github.com/markgraham924/export-monitor/discussions)
- **Discord**: Home Assistant Community (energy-management channel)

---

## Appendix: Architecture Overview

### Error Handling Flow

```
Sensor Update → Validation → Circuit Breaker Check → Update Data
     ↓ (invalid)      ↓ (fail)         ↓ (open)           ↓ (success)
Return Default    Record Failure    Raise Error    Mark Stale Detector
                                                   Clear Circuit Breaker
```

### Service Call Flow

```
Service Call → Safe Service Call (timeout: 5s) → Verify State → Success
     ↓ (error)           ↓ (timeout)          ↓ (mismatch)      ↓
Set Error State    Set Error State      Log Warning        Clear Error
Send Notification  Send Notification                       Dismiss Notification
```

### State Machine

```
IDLE → DISCHARGE_NEEDED → DISCHARGE_ACTIVE → DISCHARGE_COMPLETE → IDLE
  ↑                            ↓ (error)                              ↑
  ← ← ← ← ← ← ERROR_STATE → → → (resolved) → → → → → → → → → → → → →
```

---

## Version History

**v1.10.0** - Production Readiness Update
- Added comprehensive error handling
- Implemented sensor validation
- Added circuit breaker pattern
- Created system health monitoring
- Added persistent notifications
- Enhanced logging and diagnostics

---

## Quick Reference Card

### Critical Sensors
- ✅ System Health: `sensor.export_monitor_system_health`
- 🔴 Error State: `sensor.export_monitor_error_state`
- ⏱️ Data Staleness: `sensor.export_monitor_data_staleness`
- 🔌 Circuit Breaker: `sensor.export_monitor_circuit_breaker_status`

### Emergency Stop
```yaml
service: export_monitor.stop_discharge
```

### Health Check
All sensors should show:
- System Health: "Healthy"
- Error State: "none"
- Data Staleness: <15s
- Circuit Breaker: "Closed"

### Safe Configuration
```yaml
target_export: 0
min_soc: 25
safety_margin: 1.0
enable_auto_discharge: false  # Test manually first
```
