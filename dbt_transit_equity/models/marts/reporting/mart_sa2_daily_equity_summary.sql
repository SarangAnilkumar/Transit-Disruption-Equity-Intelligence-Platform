select
    snapshot_date,
    sa2_code,
    max(sa2_name) as sa2_name,
    max(irsd_decile) as irsd_decile,
    max(disadvantage_weight) as disadvantage_weight,
    sum(observation_count) as observation_count,
    sum(delayed_observation_count) as delayed_observation_count,
    case
        when sum(observation_count) = 0 then null
        else sum(delayed_observation_count)::decimal(18, 6)
            / sum(observation_count)::decimal(18, 6)
    end as delay_observation_rate,
    sum(disruption_alert_count) as disruption_alert_count,
    avg(disruption_score) as avg_disruption_score,
    avg(equity_impact_score) as avg_equity_impact_score,
    max(equity_impact_score) as max_equity_impact_score,
    max(equity_risk_band) as peak_equity_risk_band,
    max(score_formula_version) as score_formula_version,
    max(calculated_at) as calculated_at
from {{ ref('mart_transport_disruption_equity_score') }}
group by 1, 2
