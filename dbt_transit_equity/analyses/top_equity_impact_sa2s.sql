-- Which SA2 areas have the highest disruption equity impact?
select
    sa2_code,
    sa2_name,
    irsd_decile,
    round(equity_impact_score, 2) as equity_impact_score,
    equity_risk_band,
    observation_count,
    delayed_observation_count,
    round(delay_observation_rate * 100, 2) as delay_rate_pct,
    disruption_alert_count
from {{ ref('mart_transport_disruption_equity_score') }}
order by equity_impact_score desc nulls last
limit 25
