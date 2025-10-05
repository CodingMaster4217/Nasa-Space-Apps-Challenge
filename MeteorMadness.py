import requests
import pandas as pd
from datetime import datetime, timedelta
import math
import plotly.express as px
from IPython.display import Markdown, display

# === your NASA API key ===
API_KEY = "Z0NzPE1wXcHIFK9mqnKPbPlPoFwV3hSJncmKxn5f"   # <-- replace this with your key from https://api.nasa.gov/

# === helper functions ===
def fetch_neo_data(api_key):
    start = (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d")
    end   = datetime.utcnow().strftime("%Y-%m-%d")
    url   = "https://api.nasa.gov/neo/rest/v1/feed"
    r = requests.get(url, params={"start_date": start, "end_date": end, "api_key": api_key})
    r.raise_for_status()
    return r.json()

def parse_neo_data(data):
    rows = []
    for date, objs in data["near_earth_objects"].items():
        for o in objs:
            d = o["estimated_diameter"]["meters"]
            d_m = (d["estimated_diameter_min"] + d["estimated_diameter_max"]) / 2
            for a in o["close_approach_data"]:
                rows.append({
                    "date": date,
                    "name": o["name"],
                    "hazardous": o["is_potentially_hazardous_asteroid"],
                    "diameter_m": d_m,
                    "velocity_kmh": float(a["relative_velocity"]["kilometers_per_hour"]),
                    "miss_distance_km": float(a["miss_distance"]["kilometers"]),
                })
    return pd.DataFrame(rows)

def diameter_to_mass(d_m, density=2.6):
    r = d_m/2
    return (4/3)*math.pi*r**3*density*1000

def kinetic_energy(m, v_kms):
    v_ms = v_kms*1000
    return 0.5*m*v_ms**2

def damage_radius(energy_mt):
    return 10*(energy_mt)**(1/3)

def simulate_impact(d_m, v_kms, mitigation=None, delta_v=0):
    m = diameter_to_mass(d_m)
    if mitigation=="kinetic": v_kms = max(0, v_kms-delta_v)
    elif mitigation=="gravity": v_kms*=0.995
    elif mitigation=="nuclear": m*=0.5; v_kms*=1.05
    E = kinetic_energy(m,v_kms)
    E_mt = E/4.184e15
    R_km = damage_radius(E_mt)
    return {"energy_mt":E_mt,"damage_km":R_km}

# === fetch and compute ===
data = fetch_neo_data(API_KEY)
df = parse_neo_data(data)
display(Markdown(f"### NASA NEO records loaded: {len(df)} objects."))

# attach predicted consequences + mitigation from *real* data
records=[]
for _,r in df.iterrows():
    base = simulate_impact(r.diameter_m, r.velocity_kmh/1000)
    kin  = simulate_impact(r.diameter_m, r.velocity_kmh/1000,"kinetic",0.2)
    gra  = simulate_impact(r.diameter_m, r.velocity_kmh/1000,"gravity")
    nuc  = simulate_impact(r.diameter_m, r.velocity_kmh/1000,"nuclear")
    records.append({
        **r,
        "energy_mt":base["energy_mt"],
        "damage_km":base["damage_km"],
        "kinetic_km":kin["damage_km"],
        "gravity_km":gra["damage_km"],
        "nuclear_km":nuc["damage_km"]
    })
df=pd.DataFrame(records)

# === rich hover info ===
df["hover"] = df.apply(lambda r:
    f"<b>{r['name']}</b><br>"
    f"Date: {r['date']}<br>"
    f"Diameter: {r['diameter_m']:.1f} m<br>"
    f"Velocity: {r['velocity_kmh']:.0f} km/h<br>"
    f"Miss distance: {r['miss_distance_km']:.0f} km<br><br>"
    f"<b>Predicted impact</b><br>"
    f"Energy ≈ {r['energy_mt']:.1f} Mt TNT<br>"
    f"Damage radius ≈ {r['damage_km']:.1f} km<br><br>"
    f"<b>Mitigation strategies</b><br>"
    f"Kinetic impactor → {r['kinetic_km']:.1f} km<br>"
    f"Gravity tractor → {r['gravity_km']:.1f} km<br>"
    f"Nuclear detonation → {r['nuclear_km']:.1f} km",
    axis=1)

# === interactive scatter plot ===
fig = px.scatter(
    df,
    x="miss_distance_km",
    y="velocity_kmh",
    size="diameter_m",
    color="energy_mt",
    color_continuous_scale="inferno",
    hover_name="name",
    custom_data=["hover"],
    title="NASA Near-Earth Objects — Impact and Mitigation Scenarios",
    labels={"miss_distance_km":"Miss distance (km)","velocity_kmh":"Velocity (km/h)","energy_mt":"Impact Energy (Mt TNT)"},
    height=700
)
fig.update_traces(hovertemplate="%{customdata[0]}<extra></extra>",
                  marker=dict(opacity=0.75,line=dict(width=0.5,color="black")))
fig.update_layout(xaxis=dict(type="log"),yaxis=dict(type="log"))
fig.show()
