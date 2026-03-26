"""Tesla / vehicle adapter interface.

TODO: Implement after scaffolding is approved. (Phase 3+)
Required credentials: TESLA_ACCESS_TOKEN, TESLA_REFRESH_TOKEN

Capabilities:
- get_vehicle_state() -> VehicleState
- get_charge_state() -> ChargeState
- get_climate_state() -> ClimateState
- start_climate(temp) -> None
- lock() -> None
- unlock() -> None
- honk() -> None
- get_location() -> Location
- is_charging() -> bool
- get_range_miles() -> float
"""
