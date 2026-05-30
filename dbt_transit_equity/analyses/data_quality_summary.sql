-- Data quality and coverage limitations for Milestone 6 marts.
select 'mart_transport_disruption_equity_score' as dataset, count(*) as row_count
from {{ ref('mart_transport_disruption_equity_score') }}
union all
select 'rows_missing_sa2_in_trip_delays', count(*)
from {{ ref('int_trip_delay_events') }}
where sa2_code is null
union all
select 'rows_missing_sa2_in_alerts', count(*)
from {{ ref('int_service_alert_events') }}
where sa2_code is null
union all
select 'sa2_with_zero_observations', count(*)
from {{ ref('mart_transport_disruption_equity_score') }}
where observation_count = 0
