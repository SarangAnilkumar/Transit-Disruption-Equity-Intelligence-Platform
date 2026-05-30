-- Analytical question: Do lower SEIFA deciles show higher disruption equity impact?
-- Source mart: mart_seifa_disruption_comparison
-- Interpretation: Compare avg_equity_impact_score across deciles; not causal.
select
    irsd_decile,
    sa2_count,
    avg_equity_impact_score,
    avg_disruption_score,
    avg_delay_observation_rate,
    total_observations,
    total_delayed_observations
from {{ ref('mart_seifa_disruption_comparison') }}
order by irsd_decile
