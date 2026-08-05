# Demographic-to-auto market linkage

The market bridge keeps sourced facts separate from planning assumptions.

## Direct links

- A selected province maps directly to the corresponding geography in the 2015 AIA productivity benchmark.
- A selected municipality or FSA inherits its province's AIA region because the historical report did not publish municipal or postal-region auto benchmarks.
- Manitoba and Saskatchewan map to `Prairies`; Newfoundland and Labrador, Prince Edward Island, Nova Scotia and New Brunswick map to `Atlantic`.
- Yukon, Northwest Territories and Nunavut use the national Canada benchmark because no separate territory benchmark was published.
- Every AIA result remains labelled as a 2015 historical survey benchmark, including shop-size cohort and sample size.

## User-controlled assumptions

The demand scenario starts with the observed 2021 occupied-household count and applies four editable assumptions:

1. vehicles per occupied household;
2. annual auto care spending per vehicle;
3. shops serving the selected market; and
4. target market share.

The calculations are:

```text
estimated vehicles = occupied households × vehicles per household
annual auto care pool = estimated vehicles × annual spend per vehicle
pool per serving shop = annual auto care pool ÷ shops serving market
target-share revenue = annual auto care pool × target market share
```

These outputs are directional planning lenses, not forecasts. They must not be represented as observed vehicle registrations, current consumer spending, addressable-market commitments or expected shop revenue.

## Future authoritative links

Vehicle registrations, vehicle age, kilometres travelled, licensed repair-shop counts and current repair/maintenance spending should replace individual assumptions when AIA Canada licenses or publishes suitable province/municipality/FSA-compatible sources. Each future source needs a geography concordance, reference period, licence, refresh schedule and suppression policy.
