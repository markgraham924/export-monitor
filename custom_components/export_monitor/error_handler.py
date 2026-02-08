"""Error handling and validation utilities for Energy Export Monitor."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Service call timeout (seconds)
SERVICE_CALL_TIMEOUT = 5.0

# State verification polling settings
STATE_VERIFICATION_POLL_INTERVAL = 0.2  # Check every 200ms
STATE_VERIFICATION_MAX_WAIT = 3.0  # Maximum time to wait for state update

# Sensor value ranges for validation
SENSOR_RANGES = {
    "soc": (0.0, 100.0),  # Battery SOC in %
    "energy": (0.0, 1000.0),  # Energy values in kWh (0-1000 kWh max)
    "power": (-50000.0, 50000.0),  # Power values in W (-50kW to +50kW)
}


class ServiceCallError(Exception):
    """Exception raised when a service call fails."""
    pass


class SensorValidationError(Exception):
    """Exception raised when sensor validation fails."""
    pass


class CircuitBreaker:
    """Circuit breaker pattern for handling repeated failures."""

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_duration: int = 60,
        name: str = "circuit_breaker"
    ):
        """Initialize circuit breaker."""
        self.failure_threshold = failure_threshold
        self.timeout_duration = timeout_duration
        self.name = name
        self.failure_count = 0
        self.last_failure_time: datetime | None = None
        self.is_open = False

    def record_success(self) -> None:
        """Record a successful operation."""
        self.failure_count = 0
        self.is_open = False

    def record_failure(self) -> None:
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.failure_count >= self.failure_threshold:
            self.is_open = True
            _LOGGER.error(
                "Circuit breaker '%s' opened after %d failures",
                self.name,
                self.failure_count,
            )

    def can_attempt(self) -> bool:
        """Check if we can attempt an operation."""
        if not self.is_open:
            return True

        # Check if timeout has elapsed
        if self.last_failure_time:
            time_since_failure = datetime.now() - self.last_failure_time
            if time_since_failure > timedelta(seconds=self.timeout_duration):
                _LOGGER.info("Circuit breaker '%s' attempting reset", self.name)
                self.is_open = False
                self.failure_count = 0
                return True

        return False

    def get_status(self) -> dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "is_open": self.is_open,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
        }


async def safe_service_call(
    hass: HomeAssistant,
    domain: str,
    service: str,
    service_data: dict[str, Any],
    entity_id: str | None = None,
    expected_value: Any | None = None,
    timeout: float = SERVICE_CALL_TIMEOUT,
) -> bool:
    """
    Safely call a service with timeout and validation.
    
    Args:
        hass: Home Assistant instance
        domain: Service domain
        service: Service name
        service_data: Service data
        entity_id: Optional entity ID to verify state after call
        expected_value: Expected entity state value after call
        timeout: Timeout in seconds
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Call service with timeout
        await asyncio.wait_for(
            hass.services.async_call(
                domain,
                service,
                service_data,
                blocking=True,
            ),
            timeout=timeout,
        )

        # If entity_id provided, verify state changed
        if entity_id and expected_value is not None:
            # Poll for state update with configurable retry logic
            # Treat UNKNOWN/UNAVAILABLE as "not yet updated" during retry window
            poll_start = asyncio.get_running_loop().time()
            expected_str = str(expected_value)
            last_state = None
            
            while True:
                elapsed = asyncio.get_running_loop().time() - poll_start
                
                # Check if we've exceeded the maximum wait time
                if elapsed > STATE_VERIFICATION_MAX_WAIT:
                    if last_state and last_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                        _LOGGER.error(
                            "Entity %s state still %s after %.1fs; cannot verify expected value %s",
                            entity_id,
                            last_state.state,
                            elapsed,
                            expected_value,
                        )
                    else:
                        _LOGGER.error(
                            "Entity %s state verification timeout after %.1fs: got %s, expected %s",
                            entity_id,
                            elapsed,
                            last_state.state if last_state else "None",
                            expected_str,
                        )
                    return False
                
                state = hass.states.get(entity_id)
                last_state = state
                
                if state is None:
                    _LOGGER.warning("Entity %s not found, retrying...", entity_id)
                    await asyncio.sleep(STATE_VERIFICATION_POLL_INTERVAL)
                    continue
                
                # If state is unknown or unavailable, continue polling (integration may be updating)
                if state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                    await asyncio.sleep(STATE_VERIFICATION_POLL_INTERVAL)
                    continue
                
                # Check if state matches expected value (direct string match)
                if state.state == expected_str:
                    _LOGGER.debug(
                        "Entity %s verified after %.1fs: %s",
                        entity_id,
                        elapsed,
                        state.state,
                    )
                    return True
                
                # Try numeric comparison with tolerance for float values
                try:
                    state_val = float(state.state)
                    expected_val = float(expected_value)
                    if abs(state_val - expected_val) <= 0.01:
                        _LOGGER.debug(
                            "Entity %s verified (numeric) after %.1fs: %s ≈ %s",
                            entity_id,
                            elapsed,
                            state.state,
                            expected_str,
                        )
                        return True
                except (ValueError, TypeError):
                    pass  # Not a numeric value, continue with string comparison
                
                # State doesn't match, but it's a valid state
                # This could mean the integration responded but with wrong value
                # Continue polling in case it's still updating
                await asyncio.sleep(STATE_VERIFICATION_POLL_INTERVAL)

        return True

    except asyncio.TimeoutError:
        _LOGGER.error(
            "Service call timeout: %s.%s (timeout: %.1fs)",
            domain,
            service,
            timeout,
        )
        return False
    except Exception as err:
        _LOGGER.error(
            "Service call failed: %s.%s - %s",
            domain,
            service,
            str(err),
        )
        return False


def validate_sensor_value(
    entity_id: str,
    value: float,
    sensor_type: str,
    custom_range: tuple[float, float] | None = None,
) -> bool:
    """
    Validate sensor value is within reasonable range.
    
    Args:
        entity_id: Entity ID for logging
        value: Value to validate
        sensor_type: Type of sensor (soc, energy, power)
        custom_range: Optional custom min/max range
    
    Returns:
        True if valid, False otherwise
    """
    if custom_range:
        min_val, max_val = custom_range
    elif sensor_type in SENSOR_RANGES:
        min_val, max_val = SENSOR_RANGES[sensor_type]
    else:
        _LOGGER.warning("Unknown sensor type: %s, skipping validation", sensor_type)
        return True

    if not min_val <= value <= max_val:
        _LOGGER.error(
            "Sensor %s value %.2f outside valid range [%.1f, %.1f]",
            entity_id,
            value,
            min_val,
            max_val,
        )
        return False

    return True


def get_safe_sensor_value(
    hass: HomeAssistant,
    entity_id: str,
    sensor_type: str,
    default: float | None = None,
    custom_range: tuple[float, float] | None = None,
) -> float | None:
    """
    Safely get sensor value with validation.
    
    Args:
        hass: Home Assistant instance
        entity_id: Entity ID to read
        sensor_type: Type of sensor (soc, energy, power)
        default: Default value if sensor unavailable
        custom_range: Optional custom min/max range
    
    Returns:
        Sensor value or default if unavailable/invalid
    """
    state = hass.states.get(entity_id)
    
    if state is None:
        _LOGGER.warning("Sensor %s not found", entity_id)
        return default
    
    if state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]:
        _LOGGER.warning("Sensor %s is unavailable", entity_id)
        return default

    try:
        value = float(state.state)
        
        if not validate_sensor_value(entity_id, value, sensor_type, custom_range):
            return default
        
        return value
        
    except (ValueError, TypeError) as err:
        _LOGGER.error(
            "Cannot convert sensor %s value '%s' to float: %s",
            entity_id,
            state.state,
            str(err),
        )
        return default


class StaleDataDetector:
    """Detect when data is stale and should not be used."""

    def __init__(self, max_age_seconds: int = 30):
        """Initialize stale data detector."""
        self.max_age_seconds = max_age_seconds
        self.last_update: datetime | None = None

    def record_update(self) -> None:
        """Record a successful data update."""
        self.last_update = datetime.now()

    def is_stale(self) -> bool:
        """Check if data is stale."""
        if self.last_update is None:
            return True

        age = datetime.now() - self.last_update
        return age > timedelta(seconds=self.max_age_seconds)

    def get_age_seconds(self) -> float | None:
        """Get age of data in seconds."""
        if self.last_update is None:
            return None
        
        age = datetime.now() - self.last_update
        return age.total_seconds()

    def get_status(self) -> dict[str, Any]:
        """Get detector status."""
        return {
            "is_stale": self.is_stale(),
            "age_seconds": self.get_age_seconds(),
            "last_update": self.last_update.isoformat() if self.last_update else None,
        }
