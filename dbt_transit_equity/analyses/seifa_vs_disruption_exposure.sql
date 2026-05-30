-- How does SEIFA disadvantage overlap with disruption exposure?
select
    case
        when irsd_decile <= 3 then 'most_disadvantaged_deciles_1_3'
        when irsd_decile <= 7 then 'middle_deciles_4_7'
        else 'least_disadvantaged_deciles_8_10'
    end as seifa_decile_band,
    count(*) as sa2_hour_rows,
    round(avg(equity_impact_score), 2) as avg_equity_impact_score,
    round(avg(disruption_score), 2) as avg_disruption_score,
    round(avg(delay_observation_rate) * 100, 2) as avg_delay_rate_pct,
    sum(disruption_alert_count) as total_disruption_alerts
from {{ ref('mart_transport_disruption_equity_score') }}
where irsd_decile is not null
group by 1
order by avg_equity_impact_score desc
