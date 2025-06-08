---
title: Occupancy
---

```sql site
SELECT * 
FROM nobil_data.site 
ORDER BY site_id
```
```sql charger
SELECT * FROM nobil_data.charger
```


```sql site_location
SELECT 
    site_name, site_id, latitude, longitude, 
    "owner", operator, "Real-time information" as real_time, 
    COUNT(charger_id) as no_of_chargers
from site
LEFT JOIN nobil_data.charger USING (site_id)
WHERE operator in ${inputs.selected_operators.value}
GROUP BY (site_id, site_name, latitude, longitude, 
    "owner", operator, "Real-time information")
```

```sql site_session
SELECT  "start", "end",
make_timestamp(("start" * 1000 * 1000)::BIGINT) as start_ts, 
make_timestamp(("end" * 1000 * 1000)::BIGINT) as end_ts, 
duration,
charger_id
FROM nobil_data.session 
WHERE site_id = '${inputs.selected_site.site_id}' 
AND duration > 120
    AND '${inputs.date_range_occupancy.start}' < end_ts 
    AND '${inputs.date_range_occupancy.end}' > start_ts
ORDER BY start_dt, duration
```

```sql site_occupancy
WITH time_series AS (
  SELECT "start" as ts FROM ${site_session} UNION
  SELECT "end" as ts FROM ${site_session}
)
SELECT 
  make_timestamp((ts * 1000 * 1000)::BIGINT) as ts,
  COUNT(charger_id) AS active_sessions,
  COUNT(charger_id) / ${inputs.selected_site.no_of_chargers == true ? 1 : inputs.selected_site.no_of_chargers} as occupancy_pct
FROM 
  time_series
LEFT JOIN 
  ${site_session} ss
ON 
  (ts) BETWEEN ss.start AND (ss.end - 1)
GROUP BY 
  ts
ORDER BY 
  ts;
```

<!-- Search for operator -->
<Dropdown 
    data={site} 
    name=selected_operators 
    value=operator 
    title="Select an operator" 
    selectAllByDefault=true
    multiple=true
/>

<br />
<!-- Date range -->
<DateRange
    name="date_range_occupancy"
    defaultValue={'Last 90 Days'}
/>

<PointMap 
    data={site_location} 
    lat=latitude 
    long=longitude  
    pointName=site_name 
    name=selected_site
    startingZoom=5
    tooltip={[
        {id: 'site_id'}
    ]}
    height=400
/>
<!-- <Details title="Debug data">
<pre class="text-sm">{JSON.stringify(inputs, null, 2)}</pre>
</Details> -->

{#if inputs.selected_site.site_id == true}
No selected site

{:else }
### Selected site: {inputs.selected_site.site_name}

Operator: {inputs.selected_site.operator}
<!-- TODO session length histogram -->

### Occupancy
<LineChart
    data={site_occupancy}
    x=ts
    y=occupancy_pct
    yAxisTitle='Active Sessions'
    step=true
    xFmt='yyyy-mm-dd HH:MM'
/>
{/if}