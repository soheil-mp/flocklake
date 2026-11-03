# flocklake-core

The radar aeroecology physics and data formats used by [FlockLake](https://github.com/soheil-mp/flocklake):
reflectivity and bird density, profile integration (VID, MTR, ...), circular statistics and
night calendars. It has no network or service dependencies, so it can be used and tested on its
own.

The methods and their references are described in
[radar aeroecology](https://github.com/soheil-mp/flocklake/blob/main/docs/research/radar-aeroecology.md).

MIT licensed.

## Modules

| Module | What it does |
| :-- | :-- |
| `flocklake_core.domain` | Radar sites (ODIM, WIGOS and ICAO ids), radar bands, profile grids, quantities with units |
| `flocklake_core.reflectivity` | dBZ ↔ Z ↔ η ↔ bird density |
| `flocklake_core.bands` | Overlap weights of profile layers with an altitude band (for example the 25–300 m rotor band) |
| `flocklake_core.integrate` | VID, VIR, MTR, RTR, mean and quantile heights, direction-specific traffic, MT over a night; written rules for gaps and missing values |
| `flocklake_core.circular` | Mean direction, resultant length, angular deviation; wind "from" and movement "towards" conversions |
| `flocklake_core.nights` | Sunset to sunrise (or civil twilight) per radar and night date, polar day and night, partition windows |

```python
from datetime import date

from flocklake_core.integrate import integrate_profile
from flocklake_core.nights import night_window

night = night_window(52.953, 4.791, date(2026, 10, 15))  # Den Helder
print(night.start, night.end, night.length)

result = integrate_profile([10.0] * 25, [110.0] * 25, [10.0] * 25, [180.0] * 25)
print(float(result.vid), float(result.mtr))  # 50.0 birds/km², 1800.0 birds/km/h
```
