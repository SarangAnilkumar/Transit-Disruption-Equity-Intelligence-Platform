-- Fail when equity impact scores fall outside documented 0-100 range.
select *
from {{ ref('mart_transport_disruption_equity_score') }}
where equity_impact_score < 0
   or equity_impact_score > 100
