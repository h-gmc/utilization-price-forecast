---
title: Data debug
---

```sql missing_sites
SELECT site_id, site_id[:3] as country
  FROM nobil_data.session 
  LEFT JOIN nobil_data.site using (site_id)
  WHERE site_name IS NULL 
  AND country = 'SWE'
GROUP BY site_id
```