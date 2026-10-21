import csv, io, json, math, os, zipfile
import requests
import pandas as pd

GTFS_URL = "https://www.data.gouv.fr/api/1/datasets/r/5339d96c-6d20-4a01-939a-40f7b56d6cc1"

def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))

def fetch_gtfs_zip(retries=4, backoff=5):
    import time
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(GTFS_URL, timeout=(15, 60))
            resp.raise_for_status()
            return zipfile.ZipFile(io.BytesIO(resp.content))
        except requests.exceptions.RequestException as e:
            last_error = e
            print(f"  GTFS download attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(backoff * attempt)
    raise RuntimeError(f"Could not download GTFS after {retries} attempts") from last_error

def nearest_commune(lat, lon, communes):
    best_name, best_dist = None, None
    for c in communes:
        d = haversine_km(lat, lon, c["lat"], c["lon"])
        if best_dist is None or d < best_dist:
            best_dist, best_name = d, c["commune"]
    return best_name

def supply_vs_population(freq, communes_df):
    # Population is only a proxy for demand (see Reflection 8): it counts where
    # people live, not where they travel to.
    per_commune = freq.groupby("nearest_commune").agg(
        n_stops=("stop_id", "size"),
        daily_stop_visits=("daily_trip_count", "sum"),
        busiest_stop_visits=("daily_trip_count", "max"),
    ).reset_index().rename(columns={"nearest_commune": "commune"})
    busiest = (freq.sort_values("daily_trip_count", ascending=False)
                   .drop_duplicates("nearest_commune")
                   [["nearest_commune", "stop_name"]]
                   .rename(columns={"nearest_commune": "commune", "stop_name": "busiest_stop"}))

    # Left join from communes so a commune with no stop at all still shows up (with 0).
    supply = communes_df[["commune", "population"]].merge(per_commune, on="commune", how="left")
    supply = supply.merge(busiest, on="commune", how="left")
    supply[["n_stops", "daily_stop_visits", "busiest_stop_visits"]] = (
        supply[["n_stops", "daily_stop_visits", "busiest_stop_visits"]].fillna(0).astype(int)
    )
    supply["busiest_stop"] = supply["busiest_stop"].fillna("")

    supply["stop_visits_per_1000"] = (supply["daily_stop_visits"] / supply["population"] * 1000).round(1)
    supply["stops_per_1000"] = (supply["n_stops"] / supply["population"] * 1000).round(2)
    # Share of the commune's visits made at its single busiest stop: a high value
    # means one depot/interchange may be inflating the metric.
    supply["busiest_stop_share"] = (
        supply["busiest_stop_visits"] / supply["daily_stop_visits"].where(supply["daily_stop_visits"] > 0)
    ).fillna(0).round(2)

    supply = supply.sort_values("stop_visits_per_1000", ascending=False).reset_index(drop=True)
    supply.insert(0, "rank", supply.index + 1)
    return supply

def main():
    communes_df = pd.read_csv("data/reference/communes.csv")
    communes = communes_df.to_dict("records")

    print("Downloading SETRAM static GTFS feed...")
    zf = fetch_gtfs_zip()

    # dtype=str throughout: stop_id/route_id/trip_id mix numeric-looking and
    # non-numeric values (e.g. "FLEX-381") across GTFS files -- letting pandas
    # infer dtypes per-file causes silent int64-vs-object merge failures.
    routes = pd.read_csv(zf.open("routes.txt"), dtype=str)
    stops = pd.read_csv(zf.open("stops.txt"), dtype=str)
    trips = pd.read_csv(zf.open("trips.txt"), dtype=str)
    calendar = pd.read_csv(zf.open("calendar.txt"), dtype=str)
    stop_times = pd.read_csv(zf.open("stop_times.txt"), usecols=["trip_id", "stop_id"], dtype=str)
    stops["stop_lat"] = stops["stop_lat"].astype(float)
    stops["stop_lon"] = stops["stop_lon"].astype(float)
    print(f"Loaded {len(routes)} routes, {len(stops)} stops, {len(trips)} trips, {len(stop_times)} stop_times")

    # Pick a representative weekday: the Tuesday service pattern with the
    # longest validity window (avoids picking a one-off exception date).
    calendar["date_span"] = (
        pd.to_datetime(calendar["end_date"], format="%Y%m%d")
        - pd.to_datetime(calendar["start_date"], format="%Y%m%d")
    )
    tue_services = calendar[calendar["tuesday"] == "1"].sort_values("date_span", ascending=False)
    if tue_services.empty:
        raise RuntimeError("No Tuesday service found in calendar.txt -- feed structure may have changed")
    service_id = tue_services.iloc[0]["service_id"]
    print(f"Using service_id={service_id} as the representative weekday")

    weekday_trip_ids = set(trips[trips["service_id"] == service_id]["trip_id"])
    weekday_stop_times = stop_times[stop_times["trip_id"].isin(weekday_trip_ids)]

    freq = weekday_stop_times.groupby("stop_id").size().reset_index(name="daily_trip_count")
    freq = freq.merge(
        stops[["stop_id", "stop_name", "stop_lat", "stop_lon", "wheelchair_boarding"]],
        on="stop_id", how="left",
    ).dropna(subset=["stop_lat"])

    print(f"Assigning {len(freq)} stops to nearest of {len(communes)} communes...")
    freq["nearest_commune"] = freq.apply(
        lambda row: nearest_commune(row["stop_lat"], row["stop_lon"], communes), axis=1
    )

    freq = freq.sort_values("daily_trip_count", ascending=False)
    os.makedirs("data/gtfs_static", exist_ok=True)
    freq.to_csv("data/gtfs_static/stops_frequency.csv", index=False)
    routes[["route_id", "route_short_name", "route_long_name", "route_type"]].to_csv(
        "data/gtfs_static/routes.csv", index=False
    )
    print(f"Wrote data/gtfs_static/stops_frequency.csv ({len(freq)} rows)")
    print(f"Wrote data/gtfs_static/routes.csv ({len(routes)} rows)")
    print("Top 5 busiest stops:")
    print(freq[["stop_name", "daily_trip_count", "nearest_commune"]].head(5).to_string(index=False))

    supply = supply_vs_population(freq, communes_df)
    supply.to_csv("data/gtfs_static/supply_vs_population.csv", index=False)
    os.makedirs("docs/data", exist_ok=True)
    with open("docs/data/supply_vs_population.json", "w", encoding="utf-8") as f:
        json.dump({
            "metric": "Scheduled stop-visits per 1,000 residents on a representative weekday",
            "service_id": service_id,
            "communes": supply.to_dict("records"),
        }, f, ensure_ascii=False, indent=2)
    print(f"Wrote data/gtfs_static/supply_vs_population.csv and docs/data/supply_vs_population.json ({len(supply)} communes)")
    print(supply[["rank", "commune", "population", "n_stops", "stop_visits_per_1000", "busiest_stop_share"]].to_string(index=False))

if __name__ == "__main__":
    main()