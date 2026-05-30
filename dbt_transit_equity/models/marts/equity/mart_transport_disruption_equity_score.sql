select
    c.snapshot_date,
    c.snapshot_hour,
    c.sa2_code,
    c.sa2_name,
    eq.irsd_score,
    eq.irsd_decile,
    eq.disadvantage_weight,
    eq.route_count,
    eq.stop_count,
    e.observation_count,
    e.distinct_trip_count,
    e.distinct_stop_count,
    e.delayed_observation_count,
    e.delay_observation_rate,
    e.avg_arrival_delay_seconds,
    e.avg_departure_delay_seconds,
    e.max_delay_seconds,
    e.major_delay_count,
    e.service_alert_count,
    e.disruption_alert_count,
    c.disruption_score,
    c.disadvantage_score,
    c.network_exposure_score,
    c.equity_impact_score,
    case
        when c.equity_impact_score >= 80 then 'very_high'
        when c.equity_impact_score >= 60 then 'high'
        when c.equity_impact_score >= 40 then 'moderate'
        when c.equity_impact_score >= 20 then 'low'
        else 'minimal'
    end as equity_risk_band,
    c.score_formula_version,
    current_timestamp as calculated_at
from {{ ref('int_transport_equity_score_components') }} as c
inner join {{ ref('int_sa2_disruption_exposure') }} as e
    on c.snapshot_date = e.snapshot_date
    and c.snapshot_hour = e.snapshot_hour
    and c.sa2_code = e.sa2_code
left join {{ ref('int_sa2_equity_context') }} as eq
    on c.sa2_code = eq.sa2_code
