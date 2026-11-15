"""F02 + F08: replan in the middle of the walk from a reported problem.

The astronaut says what happened ("there is a rock ahead", "it is steep", "I am
tired", "dust is coming"); the rule classifies the problem and builds new options from
the marked point (there is no GPS). The options are computed by the same A* (route_planning),
never by the model; the suggestion is only the order, the astronaut chooses."""

from geo import haversine_m
from voice import words

# order = priority: going back (radiation, dust, oxygen) comes before detouring; tiredness keeps the destination, lighter
PROBLEMS = {
    "radiation": {"radiation", "solar", "flare", "particle"},
    "dust": {"dust", "storm", "wind"},
    "oxygen": {"oxygen", "o2"},
    "tired": {"tired", "exhausted", "breath"},
    "obstacle": {"obstacle", "hole", "rock", "boulder", "sand", "blocked", "crack", "crater", "cliff"},
    "steep": {"steep", "slope", "uphill"},
}
GENERIC = {"problem", "problems", "trouble"}
TEXT = {
    "radiation": "Solar particle event: options to go back to the base now.",
    "dust": "Dust coming: options to go back to the base.",
    "oxygen": "Low oxygen: options to go back to the base.",
    "tired": "Tiredness: less tiring options to the destination.",
    "obstacle": "Obstacle ahead: a {radius} m detour around the point {ahead} m from here, or back to the base.",
    "steep": "Steeper terrain than forecast: continue on the smoothest path or go back to the base.",
    "other": "Problem reported: continue on the safest route or go back to the base.",
}
# (id, title, goes to "destination" or "base", A* kind, detours around the obstacle?)
OPTIONS = {
    # same priority/logic as dust: a solar particle event means shelter now,
    # not a detour -- see docs/feature-05-solar-particle-event.md.
    "radiation": [("short_return", "short return to the base", "base", "fastest", False),
                  ("safe_return", "safe return to the base", "base", "safest", False)],
    "dust": [("short_return", "short return to the base", "base", "fastest", False),
             ("safe_return", "safe return to the base", "base", "safest", False)],
    "oxygen": [("short_return", "short return to the base", "base", "fastest", False),
               ("smooth_return", "smooth return to the base", "base", "smoothest", False)],
    # tiredness does not send the astronaut back: the destination stays, on the path with least effort
    "tired": [("continue_smooth", "continue on smooth terrain", "destination", "smoothest", False),
              ("continue_short", "continue on the shortest", "destination", "fastest", False)],
    "obstacle": [("safe_detour", "safe detour", "destination", "safest", True),
                 ("fast_detour", "fast detour", "destination", "fastest", True),
                 ("short_return", "short return to the base", "base", "fastest", True)],
    "steep": [("continue_smooth", "continue on smooth terrain", "destination", "smoothest", False),
              ("smooth_return", "smooth return to the base", "base", "smoothest", False)],
    "other": [("continue_safe", "continue on the safest", "destination", "safest", False),
              ("short_return", "short return to the base", "base", "fastest", False)],
}
OBSTACLE_AHEAD_M = 25  # shortcut: "ahead" with no spoken distance becomes 25 m along the route; parse "10 meters" later
OBSTACLE_RADIUS_M = 20  # ~3 DTM pixels (5.9 m): the detour passes far enough to be seen
ALREADY_AT_BASE_M = 30  # closer than this, "go back to the base" is not an option


def classify(text: str) -> str | None:
    """Kind of the reported problem, or None if the phrase reports no problem."""
    w = words(text)
    if "gale" in w:  # "Gale crater" is the place, not an obstacle
        w = [x for x in w if x != "crater"]
    for kind, keys in PROBLEMS.items():
        if any(x in keys for x in w):  # exact: fuzzy matching confused similar words
            return kind
    return "other" if any(x in GENERIC for x in w) else None


def point_ahead(points: list, lat: float, lon: float, meters: float) -> tuple[float, float]:
    """Route point `meters` ahead of the route point nearest to (lat, lon)."""
    i = min(range(len(points)), key=lambda k: haversine_m(lat, lon, *points[k]))
    walked = 0.0
    while i + 1 < len(points) and walked < meters:
        walked += haversine_m(*points[i], *points[i + 1])
        i += 1
    return tuple(points[i])


def options(problem: str, origin: tuple, destination: tuple | None, base: tuple, current_route: list | None, plan) -> dict:
    """plan(destination, kind, avoid) -> one A* route (or an exception). Returns {routes, errors, text, obstacle}."""
    obstacle = None
    if problem == "obstacle" and current_route:
        obstacle = (*point_ahead(current_route, *origin, OBSTACLE_AHEAD_M), OBSTACLE_RADIUS_M)
    far_from_base = haversine_m(*origin, *base) > ALREADY_AT_BASE_M
    routes, errors = [], []
    for id_, title, to, kind, detours in OPTIONS[problem]:
        target = destination if to == "destination" else (base if far_from_base else None)
        if target is None:
            continue
        try:
            r = plan(target, kind, [obstacle] if detours and obstacle else None)
        except Exception as e:  # noqa: BLE001 -- no path for one option does not take down the others
            errors.append(f"{title}: {getattr(e, 'detail', e)}")
            continue
        same = next((x for x in routes if x["points"] == r["points"]), None)
        if same:  # A* gave the same path for both weights: a single option, with both names
            same["title"] += f" (= {title})"
            continue
        routes.append({**r, "type": id_, "title": title, "variant": kind})  # variant: A* weight (route forecast)
    text = TEXT[problem].format(radius=OBSTACLE_RADIUS_M, ahead=OBSTACLE_AHEAD_M)
    return {"routes": routes, "errors": errors, "text": text,
            "obstacle": obstacle and {"lat": obstacle[0], "lon": obstacle[1], "radius_m": obstacle[2]}}
