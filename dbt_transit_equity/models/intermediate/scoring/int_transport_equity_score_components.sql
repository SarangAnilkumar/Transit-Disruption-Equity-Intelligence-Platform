with exposure as (
    select * from {{ ref('int_sa2_disruption_exposure') }}
),

equity as (
    select * from {{ ref('int_sa2_equity_context') }}
),

joined as (
    select
        e.snapshot_date,
        e.snapshot_hour,
        e.sa2_code,
        e.sa2_name,
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
        eq.disadvantage_weight,
        eq.transport_access_proxy_score
    from exposure as e
    left join equity as eq on e.sa2_code = eq.sa2_code
),

bounds as (
    select
        min(coalesce(delay_observation_rate, 0)) as min_delay_rate,
        max(coalesce(delay_observation_rate, 0)) as max_delay_rate,
        min(coalesce(avg_arrival_delay_seconds, 0)) as min_avg_delay,
        max(coalesce(avg_arrival_delay_seconds, 0)) as max_avg_delay,
        min(coalesce(max_delay_seconds, 0)) as min_max_delay,
        max(coalesce(max_delay_seconds, 0)) as max_max_delay,
        min(disruption_alert_count) as min_alert_count,
        max(disruption_alert_count) as max_alert_count
    from joined
),

scaled as (
    select
        j.*,
        case
            when b.max_delay_rate = b.min_delay_rate then 0.0
            else 100.0 * (coalesce(j.delay_observation_rate, 0) - b.min_delay_rate)
                / nullif(b.max_delay_rate - b.min_delay_rate, 0)
        end as delay_frequency_score,
        case
            when b.max_avg_delay = b.min_avg_delay and b.max_max_delay = b.min_max_delay then 0.0
            else 100.0 * (
                0.6 * (coalesce(j.avg_arrival_delay_seconds, 0) - b.min_avg_delay)
                    / nullif(b.max_avg_delay - b.min_avg_delay, 0)
                + 0.4 * (coalesce(j.max_delay_seconds, 0) - b.min_max_delay)
                    / nullif(b.max_max_delay - b.min_max_delay, 0)
            )
        end as delay_severity_score,
        case
            when b.max_alert_count = b.min_alert_count then 0.0
            else 100.0 * (j.disruption_alert_count - b.min_alert_count)::decimal(18, 6)
                / nullif(b.max_alert_count - b.min_alert_count, 0)::decimal(18, 6)
        end as alert_exposure_score,
        coalesce(j.disadvantage_weight, 0.5) * 100.0 as disadvantage_score,
        coalesce(j.transport_access_proxy_score, 50.0) as network_exposure_score
    from joined as j
    cross join bounds as b
)

select
    snapshot_date,
    snapshot_hour,
    sa2_code,
    sa2_name,
    observation_count,
    delayed_observation_count,
    delay_observation_rate,
    disruption_alert_count,
    delay_frequency_score,
    delay_severity_score,
    alert_exposure_score,
    0.5 * delay_frequency_score
        + 0.3 * delay_severity_score
        + 0.2 * alert_exposure_score as disruption_score,
    disadvantage_score,
    network_exposure_score,
    (
        0.5 * delay_frequency_score
        + 0.3 * delay_severity_score
        + 0.2 * alert_exposure_score
    ) * (0.6 + 0.4 * coalesce(disadvantage_weight, 0.5)) as equity_impact_score,
    'v1_transparent_weighted_proxy' as score_formula_version
from scaled
