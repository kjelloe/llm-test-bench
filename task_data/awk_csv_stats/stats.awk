# Compute per-region sales totals from a comma-separated CSV.
# Input columns: date,region,amount  (header on row 1)
# Output: one line per region — "region: total" (two decimal places)
BEGIN {
    FS = " "
}
NR > 1 {
    totals[$2] += $3
}
END {
    for (r in totals)
        printf "%s: %.2f\n", r, totals[r]
}
