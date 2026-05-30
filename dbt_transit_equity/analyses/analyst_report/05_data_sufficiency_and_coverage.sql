-- Analytical question: Is current GTFS-R coverage sufficient for evidence-grade reporting?
-- Source: local audit output mirrored in mart row counts as proxy when Redshift unavailable.
select
    count(distinct snapshot_date) as days_in_mart,
    count(distinct snapshot_hour) as hours_in_mart,
    count(*) as sa2_hour_rows,
    count(distinct sa2_code) as sa2_count,
    sum(observation_count) as total_observations,
    case
        when count(distinct snapshot_date) < 1 then 'insufficient'
        when count(distinct snapshot_date) <= 6 then 'exploratory'
        when count(distinct snapshot_date) <= 13 then 'analyst-ready'
        else 'strong'
    end as data_sufficiency_proxy
from {{ ref('mart_transport_disruption_equity_score') }}
