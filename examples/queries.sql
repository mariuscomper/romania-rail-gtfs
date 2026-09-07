-- Curse programate pe operator.
SELECT agency_name, COUNT(*) AS trip_definitions
  FROM trips
  JOIN routes USING (route_id)
  JOIN agencies USING (agency_id)
 GROUP BY agency_id, agency_name
 ORDER BY trip_definitions DESC;

-- Stațiile cu cei mai mulți operatori.
SELECT s.stop_id, s.stop_name, COUNT(DISTINCT r.agency_id) AS operator_count
  FROM stops AS s
  JOIN stop_times AS st USING (stop_id)
  JOIN trips AS t USING (trip_id)
  JOIN routes AS r USING (route_id)
 GROUP BY s.stop_id, s.stop_name
HAVING operator_count > 1
 ORDER BY operator_count DESC, s.stop_name;

-- Opriri programate pe o stație, cu operatorul și ruta.
SELECT st.departure_time, a.agency_name, t.trip_short_name,
       r.route_long_name
  FROM stop_times AS st
  JOIN trips AS t USING (trip_id)
  JOIN routes AS r USING (route_id)
  JOIN agencies AS a USING (agency_id)
 WHERE st.stop_id = '10017'
 ORDER BY st.departure_time;

-- Ponderea serviciilor rutiere de înlocuire păstrate în feed.
SELECT COUNT(*) AS replacement_bus_trip_definitions
  FROM trips AS t
  JOIN routes AS r USING (route_id)
 WHERE r.route_type = '200';
