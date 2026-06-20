# Field Data Contract

Place the measured O-Cell curves here as two CSV files:

- `ocell_upper_plate.csv`
- `ocell_lower_plate.csv`

Required header:

```text
Load,Displacement
```

Conventions:

- `Load` uses the same force units as the PLAXIS model.
- `Displacement` uses the same length units as the PLAXIS model.
- Upper plate displacement is positive upward.
- Lower plate displacement is negative downward.
