-- Analytical question: Which routes contribute most to high-impact SA2 exposure?
-- Source marts: int_trip_delay_events + mart_sa2_multi_day_equity_summary
-- Limitation: Route attribution depends on stop-level SA2 mapping coverage.
with high_impact_sa2 as (
    select sa2_code
    from {{ ref('mart_sa2_multi_day_equity_summary') }}
    where peak_equity_risk_band in ('moderate', 'high', 'very_high')
       or avg_equity_impact_score >= 35
)

select
    d.route_id,
    count(*) as delayed_observations_in_high_impact_sa2,
    count(distinct d.sa2_code) as high_impact_sa2_count,
    count(distinct d.trip_id) as distinct_trip_count,
    avg(d.max_delay_seconds) as avg_max_delay_seconds
from {{ ref('int_trip_delay_events') }} as d
inner join high_impact_sa2 as h on d.sa2_code = h.sa2_code
where d.is_delayed_5min = true
  and d.route_id is not null
group by 1
order by delayed_observations_in_high_impact_sa2 desc nulls last
limit 25
