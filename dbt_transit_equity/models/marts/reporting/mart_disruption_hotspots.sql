select
    snapshot_date,
    snapshot_hour,
    sa2_code,
    sa2_name,
    irsd_decile,
    disadvantage_weight,
    observation_count,
    delayed_observation_count,
    delay_observation_rate,
    disruption_alert_count,
    disruption_score,
    equity_impact_score,
    equity_risk_band,
    score_formula_version,
    calculated_at
from {{ ref('mart_transport_disruption_equity_score') }}
