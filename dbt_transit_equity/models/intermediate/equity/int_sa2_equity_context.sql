with seifa as (
    select * from {{ ref('stg_seifa_sa2') }}
),

stop_counts as (
    select
        sa2_code,
        count(distinct stop_id) as stop_count
    from {{ ref('stg_stops_sa2_mapping') }}
    where is_matched = true
    group by 1
),

route_counts as (
    select
        sa2_code,
        count(distinct route_id) as route_count
    from {{ ref('stg_route_sa2_coverage') }}
    group by 1
),

joined as (
    select
        s.sa2_code,
        s.sa2_name,
        s.irsd_score,
        s.irsd_decile,
        s.irsd_percentile,
        coalesce(sc.stop_count, 0) as stop_count,
        coalesce(rc.route_count, 0) as route_count
    from seifa as s
    left join stop_counts as sc on s.sa2_code = sc.sa2_code
    left join route_counts as rc on s.sa2_code = rc.sa2_code
),

weighted as (
    select
        *,
        case
            when irsd_decile is not null then (11.0 - irsd_decile) / 10.0
            when irsd_percentile is not null then (100.0 - irsd_percentile) / 100.0
            else null
        end as disadvantage_weight_raw
    from joined
),

ranked as (
    select
        *,
        case
            when disadvantage_weight_raw is not null then disadvantage_weight_raw
            when irsd_score is not null then
                1.0 - percent_rank() over (order by irsd_score asc)
            else 0.5
        end as disadvantage_weight
    from weighted
),

access_bounds as (
    select
        min(route_count + stop_count) as min_access,
        max(route_count + stop_count) as max_access
    from ranked
)

select
    r.sa2_code,
    r.sa2_name,
    r.irsd_score,
    r.irsd_decile,
    r.irsd_percentile,
    r.disadvantage_weight,
    r.stop_count,
    r.route_count,
    case
        when ab.max_access = ab.min_access then 50.0
        else 100.0 * (r.route_count + r.stop_count - ab.min_access)::decimal(18, 6)
            / nullif(ab.max_access - ab.min_access, 0)::decimal(18, 6)
    end as transport_access_proxy_score
from ranked as r
cross join access_bounds as ab
