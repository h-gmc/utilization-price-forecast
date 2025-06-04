---
title: Occupancy
---

```sql site
SELECT * FROM nobil_data.site ORDER BY site_id
```


```sql operators
SELECT operator, count(1) as no_of_sites FROM nobil_data.site GROUP BY operator ORDER BY 2 desc
```

```sql site_owners 
SELECT "owner", count(1) as no_of_sites FROM nobil_data.site GROUP BY "owner" ORDER BY 2 desc
```

```sql site_locations
SELECT site_name, site_id, latitude, longitude, "owner", operator from site
```

```sql site_sessions
SELECT  * FROM nobil_data.session 
-- WHERE site_id = '${inputs.selected_site.site_id}'
WHERE site_id = 'SWE_47193'
AND duration > 120
ORDER BY start_dt, duration
```



<PointMap 
    data={site_locations} 
    lat=latitude 
    long=longitude  
    pointName=site_name 
    name=selected_site
    startingZoom=12
    tooltip={[
        {id: 'site_id'}
    ]}
    height=400
/>

Selected site: {inputs.selected_site.site_id}
<DataTable data={site_sessions} >
    <Column id=start_dt fmt="yyyy-mm-dd HH:MM"/>
    <Column id=duration  fmt='num0' />
</DataTable>
