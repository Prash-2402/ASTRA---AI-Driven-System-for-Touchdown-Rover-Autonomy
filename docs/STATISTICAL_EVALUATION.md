# Statistical Evaluation (`experiments/analysis/statistics.py`)

- **Completion rate:** k/n with the 95 % Wilson score interval
  `(p + z²/2n ± z√(p(1−p)/n + z²/4n²)) / (1 + z²/n)`, z = 1.96. (Verified: 5/10 → [0.237, 0.763].)
- **Continuous metrics:** mean, sample SD (ddof = 1) and n; missing values excluded and counted
  (time-to-completion only exists for successes, so its n differs).
- **Paired comparisons (matched seeds):**
  - completion: exact McNemar test (two-sided binomial on discordant pairs);
  - continuous: Wilcoxon signed-rank on pairs where both values exist; mean difference ASTRA − FSM.
- Paired-fault conditions are a separate tier and never pooled with single faults.
- Incomplete experiments are labelled INCOMPLETE in API (`complete: false`), UI and reports; statistics use only
  completed trials. With n ≤ 5 per cell, p-values are descriptive and no significance claims are made.
