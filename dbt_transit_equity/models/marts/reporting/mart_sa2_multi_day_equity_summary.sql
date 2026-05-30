select
    sa2_code,
    max(sa2_name) as sa2_name,
    max(irsd_decile) as irsd_decile,
    max(disadvantage_weight) as disadvantage_weight,
    count(distinct snapshot_date) as days_observed,
    count(distinct snapshot_hour) as snapshot_hours_observed,
    avg(equity_impact_score) as avg_equity_impact_score,
    max(equity_impact_score) as max_equity_impact_score,
    sum(case when equity_risk_band in ('high', 'very_high') then 1 else 0 end) as high_or_above_snapshot_count,
    case
        when count(*) = 0 then null
        else sum(case when equity_risk_band in ('high', 'very_high') then 1 else 0 end)::decimal(18, 6)
            / count(*)::decimal(18, 6)
    end as high_or_above_snapshot_rate,
    avg(delay_observation_rate) as avg_delay_observation_rate,
    avg(disruption_score) as avg_disruption_score,
    max(score_formula_version) as score_formula_version,
    case
        when max(equity_impact_score) >= 80 then 'very_high'
        when max(equity_impact_score) >= 60 then 'high'
        when max(equity_impact_score) >= 40 then 'moderate'
        when max(equity_impact_score) >= 20 then 'low'
        else 'minimal'
    end as peak_equity_risk_band
from {{ ref('mart_transport_disruption_equity_score') }}
group by 1
