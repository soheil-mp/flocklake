# Radar aeroecology: the science FlockLake implements

This note collects the physics, conventions and published methods the platform relies on. Each
formula here becomes a tested function in `flocklake-core` (milestone M1) or part of the profile
engine (milestone M12). Where a number is a default from published software, the note says so.

## 1. Why weather radars see birds

Operational weather radars transmit at C-band (about 5.3 cm, most of Europe) or S-band (about
10.7 cm, the US WSR-88D network). They detect anything that scatters the pulse back: rain, snow,
insects, birds, bats, smoke. Most songbirds migrate at night. Shortly after sunset they take off
almost at the same moment, and the radar shows a ring of echo spreading around the antenna. A
network of radars therefore works as a continent-wide bird sensor that already exists and
publishes its data openly (Shamoun-Baranes et al. 2014; Nilsson et al. 2019).

A single radar is summarised as a **vertical profile**: for each altitude layer and each scan
time, how many birds there are and how fast and where they move. The published standard
algorithm, vol2bird (Dokter et al. 2011, 2019), uses range gates between 5 and 35 km from the
radar and 25 layers of 200 m (0–5 km). The Aloft profiles checked for this project follow that
grid exactly (heights 0, 200, ..., 4800 m).

## 2. From reflectivity to birds

Radars report the reflectivity factor in dBZ, which is defined for raindrops. For animals the
useful quantity is the **reflectivity** η, the scattering cross-section per unit volume:

```text
Z   = 10^(dBZ / 10)                                [mm⁶ m⁻³]
η   = (10³ · π⁵ · |K|² / λ⁴) · Z                     [cm² km⁻³], λ in cm, |K|² = 0.93
ρ   = η / σ                                        [birds km⁻³]
```

σ is the radar cross-section of one bird. The convention, and the FlockLake default, is
**σ = 11 cm²** (Dokter et al. 2011). It is configurable and always stored with the output (the
`rcs` column), because density scales directly with it.

**Worked check against real data.** Aloft profile `nldhl`, 15 Oct 2026 00:00 UTC, lowest layer:
`dbz = −19.556`, `radar_wavelength = 5.3`. The formula gives η = 3.995 cm² km⁻³ and
ρ = 0.3632 birds km⁻³; the file holds `eta = 3.992` and `dens = 0.3629`. At C-band, 0 dBZ
corresponds to about 361 cm² km⁻³, or about 33 birds km⁻³.

## 3. Speed and direction (volume velocity processing)

Within one altitude layer, the Doppler radial velocity of each gate is modelled as a uniform
flow (u eastward, v northward, w upward) seen from azimuth φ and elevation θ:

```text
v_r = u · sin φ · cos θ + v · cos φ · cos θ + w · sin θ
```

A least-squares fit per layer gives u, v, w. Then:

```text
ff = √(u² + v²)                    ground speed [m/s]
dd = atan2(u, v) mod 360°          direction of movement, clockwise from north (TOWARDS)
sd_vvp = RMS of fit residuals      [m/s]
```

Checked on the same Aloft record: u = 5.864, v = 10.163 gives ff = 11.733 m/s and dd = 29.99°,
identical to the file.

- **Direction conventions differ and this is a classic bug.** Profile `dd` is the direction
  birds move *towards*. Meteorological wind direction is where the wind comes *from*. Wind
  components are `u_w = −V · sin(wd)`, `v_w = −V · cos(wd)`. FlockLake converts explicitly and
  tests the conversion.
- **`sd_vvp`** is large for birds (varied headings, flapping flight) and small for passively
  drifting rain or insects. vol2bird sets bird density to zero where `sd_vvp` is below a
  threshold: by default 2 m/s for C-band and 1 m/s for S-band (bioRad documentation).
- **`gap`** flags layers where the azimuthal coverage is too patchy for a reliable fit.
- **Velocity folding.** Radial velocities beyond the Nyquist velocity wrap around. vol2bird
  dealiases with a torus mapping (Haase & Landelius 2004); FlockLake implements the same idea.

## 4. Separating birds from weather and clutter

All rules below are deterministic and documented; there are no learned models anywhere in the
platform (see [ADR 0003](../adr/0003-physics-based-processing.md)).

- **Correlation coefficient ρHV** (dual polarisation): rain is close to 1, biological echoes are
  much lower. vol2bird's dual-polarisation mode treats gates with ρHV above 0.95 as
  precipitation.
- **Depolarisation ratio** (Kilambi et al. 2018), from differential reflectivity in linear units
  (Zdr) and ρHV:

  ```text
  DR = 10 · log10[(Zdr + 1 − 2·√Zdr·ρHV) / (Zdr + 1 + 2·√Zdr·ρHV)]     [dB]
  ```

  Values above about −12 dB indicate non-meteorological (biological) scatter.
- **Single-polarisation fallback:** contiguous reflectivity cells above a threshold are treated
  as precipitation and removed with a fringe; static clutter maps remove fixed targets.
- **Insects** drift with the wind. Low `sd_vvp` and low airspeed (ground velocity minus wind)
  identify them. FlockLake **flags** likely insect layers rather than deleting them, so analysts
  can see the decision.
- **Not used:** convolutional-network segmentation such as MistNet (Lin et al. 2019). It is
  accurate, but it is a learned model, and this project keeps every classification explainable as
  a formula plus a threshold.

## 5. Integrated quantities

With layer thickness Δh in km (0.2 km) and ff converted to km/h (× 3.6):

| Quantity | Formula | Unit | Meaning |
| :-- | :-- | :-- | :-- |
| VID | Σ ρᵢ · Δh | birds km⁻² | Birds above one square kilometre |
| VIR | Σ ηᵢ · Δh | cm² km⁻² | Reflectivity over one square kilometre |
| MTR | Σ ρᵢ · ffᵢ · Δh | birds km⁻¹ h⁻¹ | Birds crossing a 1 km line (perpendicular to their movement) per hour |
| RTR | Σ ηᵢ · ffᵢ · Δh | cm² km⁻¹ h⁻¹ | Reflectivity traffic rate |
| MT | ∫ MTR dt over a night | birds km⁻¹ | Migration traffic: total passage per night |
| Mean height | Σ hᵢ ρᵢ / Σ ρᵢ | m | Density-weighted flight altitude (layer midpoints) |

- **Direction-specific traffic:** the number crossing a line at angle α uses
  `ff · cos(dd − α)` instead of ff (as in bioRad's `integrate_profile`).
- **Altitude bands** (for example the 25–300 m band of offshore turbine rotors): each 200 m
  layer counts with its overlap fraction. For 25–300 m, the 0–200 m layer counts 175/200 and the
  200–400 m layer counts 100/200. The lowest layers are the least reliable (ground clutter, beam
  blockage, beam height growing with range), so band products carry a quality flag.

## 6. Time: nights, not calendar days

Nocturnal migration crosses midnight, so analysing by calendar day splits each night in two.
FlockLake partitions by **night**: the evening date at the radar, from sunset to the next
sunrise at the radar's coordinates (see [ADR 0008](../adr/0008-night-partitions.md)).

- Standard sunrise/sunset is the default; civil twilight (sun 6° below the horizon) is an option.
- Radars far north (Finland, Norway, Iceland) have no astronomical night around midsummer. The
  partition exists but is empty, and quality checks must expect that rather than raise alarms.
- Night length changes by hours over a season. Totals per night (MT) are therefore not the same
  as rates; FlockLake keeps both.

## 7. Wind and flight behaviour

Ground velocity **g** (from the profile) is the bird's air velocity **a** plus the wind **w**:

```text
a = g − w        airspeed = |a|, heading = direction of a
tailwind  = w · ĝ           (wind component along the track)
crosswind = w · ĝ⊥
```

Winds come from Open-Meteo or ERA5 on pressure levels. They are interpolated to each layer's
midpoint by geopotential height, not by a fixed table. Profile heights in vol2bird output are
the lower bound of each layer. Whether the reference is sea level or the radar antenna must be
confirmed per source before combining with wind data (`radar_height` is in every file): this is a
tracked verification task in milestone M1.

## 8. Why it matters

- **Offshore wind.** Since 1 July 2023 the Netherlands requires offshore wind farms to slow
  turbines to under 2 revolutions per minute during predicted mass migration at 25–300 m above
  sea level. Announcements are possible from 15 February to 15 May and from 20 September to
  30 November, capped at 60 hours a year, with 48 hours' notice. The forecast model was developed
  by the University of Amsterdam and is fed by an offshore bird radar on platform K14. Dutch
  rules define mass migration as at least 500 birds per km per hour at rotor height.
  FlockLake does **not** forecast and is **not** an operational curtailment signal. It offers an
  observation-based, retrospective view of how often and when traffic in the rotor band was high
  near the coast, with the caveat that a land-based radar samples within about 35 km.
- **Light pollution.** Heavy-migration nights matter for "lights out" campaigns (Horton et al.
  2019). FlockLake can show past heavy nights per radar.
- **Ecology.** Seasonal timing (phenology), flight altitudes, and how birds respond to wind are
  core questions in movement ecology. The data products are designed to be easy to reuse from
  R (bioRad) and Python.

## 9. Glossary

| Term | Meaning |
| :-- | :-- |
| PVOL | Polar volume: all sweeps (elevations) of one radar scan cycle |
| Sweep | One 360° rotation at a fixed elevation angle |
| Gate | One range bin along a ray |
| ODIM HDF5 | The OPERA data information model, stored as HDF5 (EUMETNET standard) |
| VP / VPTS | Vertical profile / vertical profile time series |
| VCP | Volume coverage pattern (NEXRAD scan strategy) |
| Nyquist velocity | Largest radial velocity measurable without folding |
| DBZH, VRADH, RHOHV, ZDR | ODIM quantity names: reflectivity, radial velocity, correlation coefficient, differential reflectivity |

## References

- Dokter, A. M., Liechti, F., Stark, H., Delobbe, L., Tabary, P., & Holleman, I. (2011). Bird
  migration flight altitudes studied by a network of operational weather radars. *Journal of the
  Royal Society Interface*, 8(54), 30–43.
- Dokter, A. M., Desmet, P., Spaaks, J. H., van Hoey, S., Veen, L., Verlinden, L., Nilsson, C.,
  Haase, G., Leijnse, H., Farnsworth, A., Bouten, W., & Shamoun-Baranes, J. (2019). bioRad:
  biological analysis and visualization of weather radar data. *Ecography*, 42(5), 852–860.
- Haase, G., & Landelius, T. (2004). Dealiasing of Doppler radar velocities using a torus
  mapping. *Journal of Atmospheric and Oceanic Technology*, 21(10), 1566–1573.
- Horton, K. G., Nilsson, C., Van Doren, B. M., La Sorte, F. A., Dokter, A. M., & Farnsworth, A.
  (2019). Bright lights in the big cities: migratory birds' exposure to artificial light.
  *Frontiers in Ecology and the Environment*, 17(4), 209–214.
- Kilambi, A., Fabry, F., & Meunier, V. (2018). A simple and effective method for separating
  meteorological from nonmeteorological targets using dual-polarization data. *Journal of
  Atmospheric and Oceanic Technology*, 35(7), 1415–1424.
- Kranstauber, B., Bouten, W., Leijnse, H., Wijers, B.-C., Verlinden, L., Shamoun-Baranes, J., &
  Dokter, A. M. (2020). High-resolution spatial distribution of bird movements estimated from a
  weather radar network. *Remote Sensing*, 12(4), 635.
- Lin, T.-Y., Winner, K., Bernstein, G., et al. (2019). MistNet:
  measuring historical bird migration in the US using archived weather radar data and
  convolutional neural networks. *Methods in Ecology and Evolution*, 10(11), 1908–1922.
- Nilsson, C., Dokter, A. M., Verlinden, L., et al. (2019). Revealing patterns of nocturnal
  migration using the European weather radar network. *Ecography*, 42(5), 876–886.
- Shamoun-Baranes, J., Alves, J. A., Bauer, S., Dokter, A. M., Hüppop, O., Koistinen, J.,
  Leijnse, H., Liechti, F., van Gasteren, H., & Chapman, J. W. (2014). Continental-scale radar
  monitoring of the aerial movements of animals. *Movement Ecology*, 2, 9.
- Stepanian, P. M., Horton, K. G., Melnikov, V. M., Zrnić, D. S., & Gauthreaux, S. A. (2016).
  Dual-polarization radar products for biological applications. *Ecosphere*, 7(11), e01539.
- EUMETNET OPERA. *ODIM_H5: OPERA Data Information Model for HDF5*, version 2.4.
- Aloft. *VPTS CSV: a data exchange format for vertical profile time series.*
  <https://aloftdata.eu/vpts-csv/>
- Noordzeeloket. *Start/Stop: shutting down offshore wind turbines during peak bird migration.*
  <https://noordzeeloket.nl/en/functions-use/offshore-energy-transition/offshore-wind-energy/start-stop/>

Bibliographic details were assembled from memory and the publishers' pages during planning;
milestone M20 verifies every entry against its DOI before the validation report is published.
