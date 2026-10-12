"""Build the profile city: the year as a block of towers that builds itself and is then eaten.

    python city.py [--fetch] [--freeze SECONDS]

Reads days.json, a map of date to contributions made that day, and writes
city-light.svg and city-dark.svg. Each tower is one day and is a deeper step of
blue the taller it is. Weeks run left to right and the days of the week run
front to back. The towers go up one at a time in the order the days happened;
then a yellow ball with a mouth sweeps the city row by row, front row first,
and eats each tower from the roof down, with four ghosts chasing it along the
cleared ground. The result is a single SVG animated with CSS alone, so it plays
inside a README.

--fetch first rewrites days.json from the GitHub contribution calendar for the
current year. It needs GITHUB_TOKEN and reads the account from
GITHUB_REPOSITORY_OWNER. --freeze pauses the animation at a moment in the loop,
for checking a still frame.
"""
import argparse
import datetime as dt
import json
import math
import os
import urllib.request
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.abspath(__file__))
THEMES = {
    "light": {"surface": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781", "ground": "#f0efec",
              "lot": "#e1e0d9", "window": "#eaf3fd",
              "ramp": ["#9ec5f4", "#6da7ec", "#3987e5", "#1c5cab", "#0d366b"]},
    "dark": {"surface": "#1a1a19", "ink": "#f0efec", "ink2": "#c3c2b7", "muted": "#898781", "ground": "#222221",
             "lot": "#2c2c2a", "window": "#f3d586",
             "ramp": ["#104281", "#1c5cab", "#2a78d6", "#5598e7", "#86b6ef"]},
}
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'
WIDTH, H, PAD = 840, 384, 28
SLOT, WIDE, FLOOR = 17, 12, 5
FLOORS = 35  # the tallest tower has about this many floors
NUMBERS = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
BACK_X, BACK_Y = 8, 7      # how far each row sits behind the one in front
DEEP_X, DEEP_Y = 6, 5      # the depth of one tower
GROUND = 328
# the loop, in percent: towers start going up between FIRST and LAST, each taking RISE;
# the eating runs from EAT_FROM to EAT_TO
LOOP, FIRST, LAST, RISE = 60, 2, 24, 3
EAT_FROM, EAT_TO = 32, 95
RADIUS = 13
HOP = 0.35  # how much quicker the eater crosses open ground than it eats down a tower
LAG, GAP = 2, 0.5  # the lead ghost trails by this many towers, and each later ghost by this many seconds more
GHOSTS = [("#ff9d94", "#ff3b30", "#b3140c"), ("#ffe0f1", "#ffa6d5", "#d36aa6"),
          ("#c4f9fc", "#33e0f0", "#0f9aa8"), ("#ffddb0", "#ffa83a", "#c26f08")]


def text(x, y, body, size, fill, weight=400, anchor="start"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}">{escape(str(body))}</text>')


def mix(colour, other, share):
    """Blend one hex colour toward another."""
    a, b = (tuple(int(value[i:i + 2], 16) for i in (1, 3, 5)) for value in (colour, other))
    return "#" + "".join(f"{round(x + (y - x) * share):02x}" for x, y in zip(a, b))


def size(depth):
    """The eater is drawn larger in the front rows than at the back."""
    return 1.2 - 0.06 * depth


def draw(daily, starts, t, freeze):
    weeks = len(starts)
    W = max(WIDTH, weeks * SLOT + 6 * BACK_X + DEEP_X + 2 * PAD + 24)  # a full year is wider than the page
    left = (W - weeks * SLOT - 6 * BACK_X - DEEP_X) / 2 + 4
    peak_day = max(daily, key=daily.get)
    per_floor = max(1, math.ceil(daily[peak_day] / FLOORS))
    tallest = -(-daily[peak_day] // per_floor) * FLOOR
    every = "each one" if per_floor == 1 else f"every {NUMBERS[per_floor] if per_floor < len(NUMBERS) else per_floor}"

    def lot(week, depth):
        return left + week * SLOT + depth * BACK_X, GROUND - depth * BACK_Y

    def height(week, depth):
        return -(-daily.get(starts[week] + dt.timedelta(days=6 - depth), 0) // per_floor) * FLOOR

    def at(moment):
        return EAT_FROM + (EAT_TO - EAT_FROM) * moment / clock

    # the route: front row first, each row in the opposite direction to the last, so nothing
    # still standing is ever in front of the eater
    route = [(week, depth) for depth in range(7) for week in (range(weeks) if depth % 2 == 0 else reversed(range(weeks)))
             if height(week, depth)]
    stops, clock, here = [], 0.0, (-30.0, GROUND - 40.0)
    for week, depth in route:
        x, base = lot(week, depth)
        h = height(week, depth)
        cx, rest = x + WIDE / 2 + DEEP_X / 2, base - DEEP_Y / 2 - RADIUS * size(depth) * 0.5
        clock += 6 + HOP * math.dist(here, (cx, rest - h))
        begin = clock
        clock += h
        here = (cx, rest)
        stops.append((week, depth, cx, rest, h, begin, clock))
    eaten = {(week, depth): (at(begin), at(end)) for week, depth, _, _, _, begin, end in stops}

    css = [f"text{{font-family:{FONT}}}",
           f".b,.pac,.peak{{animation-duration:{LOOP}s;animation-iteration-count:infinite;animation-timing-function:linear}}",
           ".jl,.jr{animation:.18s linear infinite alternate}.jl{animation-name:jl}.jr{animation-name:jr}"
           "@keyframes jl{from{transform:rotate(3deg)}to{transform:rotate(40deg)}}"
           "@keyframes jr{from{transform:rotate(-3deg)}to{transform:rotate(-40deg)}}"]
    first, last = stops[0], stops[-1]
    away = f"transform:translate(-30px,{first[3] - first[4]:.1f}px) scale({size(first[1]):.2f})"
    walk = [f"0%,{EAT_FROM - 2}%{{{away}}}"]
    for week, depth, cx, rest, h, begin, end in stops:
        walk.append(f"{at(begin):.3f}%{{transform:translate({cx:.1f}px,{rest - h:.1f}px) scale({size(depth):.2f})}}"
                    f"{at(end):.3f}%{{transform:translate({cx:.1f}px,{rest:.1f}px) scale({size(depth):.2f})}}")
    walk.append(f"{EAT_TO + 3}%{{transform:translate({W + 40}px,{last[3]:.1f}px) scale({size(last[1]):.2f})}}"
                f"{EAT_TO + 3.01}%,100%{{{away}}}")
    css.append(f"@keyframes pac{{{''.join(walk)}}}.pac{{animation-name:pac}}")

    # the ghosts run along the ground through lots that are already cleared: the lead one is
    # always LAG towers behind the eater, and the others follow the same path a moment later
    def ground(index):
        if index < 0:
            return f"transform:translate({-30 + 30 * index}px,{GROUND - 14}px) scale({size(0):.2f})"
        _, depth, cx, rest, _, _, _ = stops[index]
        return f"transform:translate({cx:.1f}px,{rest + RADIUS * size(depth) * 0.5 - 10 * size(depth):.1f}px) scale({size(depth):.2f})"

    chase = [f"0%,{EAT_FROM - 2}%{{{ground(-LAG)}}}"]
    chase += [f"{at(stop[5]):.3f}%{{{ground(index - LAG)}}}" for index, stop in enumerate(stops)]
    chase.append(f"{at(clock):.3f}%{{{ground(len(stops) - 1)}}}"
                 f"{EAT_TO + 3}%{{transform:translate({W + 40}px,{last[3]:.1f}px) scale({size(last[1]):.2f})}}"
                 f"{EAT_TO + 3.01}%,100%{{{ground(-LAG)}}}")
    css.append(f"@keyframes ghost{{{''.join(chase)}}}.ghost{{animation:ghost {LOOP}s linear infinite}}"
               ".float{animation:float .3s ease-in-out infinite alternate}@keyframes float{to{transform:translateY(-2px)}}")
    for index in range(len(GHOSTS)):
        behind = index * GAP if freeze is None else index * GAP - freeze
        css.append(f".g{index}{{animation-delay:{behind % LOOP - LOOP:.2f}s}}")

    defs = ['<radialGradient id="ball" gradientUnits="userSpaceOnUse" cx="-4" cy="-5" r="19">'
            '<stop offset="0" stop-color="#fff3a6"/><stop offset=".45" stop-color="#ffd21f"/><stop offset="1" stop-color="#c98500"/></radialGradient>']
    for index, (light, body, shade) in enumerate(GHOSTS):
        defs.append(f'<radialGradient id="g{index}" gradientUnits="userSpaceOnUse" cx="-4" cy="-6" r="20"><stop offset="0" stop-color="{light}"/>'
                    f'<stop offset=".45" stop-color="{body}"/><stop offset="1" stop-color="{shade}"/></radialGradient>')
    lots, towers, peak = [], [], ""
    for depth in range(6, -1, -1):  # Monday at the back, Sunday at the front
        weekday = 6 - depth
        base = GROUND - depth * BACK_Y
        defs.append(f'<pattern id="win{depth}" x="{left + depth * BACK_X:.1f}" y="{base % FLOOR}" width="{SLOT}" height="{FLOOR}" '
                    f'patternUnits="userSpaceOnUse"><rect x="2" y="1.5" width="3" height="2" fill="{t["window"]}"/>'
                    f'<rect x="7" y="1.5" width="3" height="2" fill="{t["window"]}"/></pattern>')
        for week in range(weeks):
            x, _ = lot(week, depth)
            lots.append(f'<path d="M{x:.1f},{base}h{WIDE}l{DEEP_X},-{DEEP_Y}h-{WIDE}z" fill="{t["lot"]}"/>')
            h = height(week, depth)
            if not h:
                continue
            name = f"k{week}_{depth}"
            sunk = h + DEEP_Y + 1
            # taller towers take a further step along the blue ramp, as on a heatmap
            front = t["ramp"][min(4, int(5 * math.sqrt(h / (tallest + 1))))]
            side, top = mix(front, "#000000", 0.28), mix(front, "#ffffff", 0.35)
            grown = FIRST + (LAST - FIRST) * (week * 7 + weekday) / (weeks * 7 - 1)
            bite, gone = eaten[(week, depth)]
            css.append(f"@keyframes {name}{{0%{{transform:translateY({sunk}px)}}"
                       f"{grown:.2f}%{{transform:translateY({sunk}px);animation-timing-function:cubic-bezier(.2,.8,.3,1)}}"
                       f"{grown + RISE:.2f}%{{transform:translateY(0)}}{bite:.3f}%{{transform:translateY(0)}}"
                       f"{gone:.3f}%,100%{{transform:translateY({sunk}px)}}}}.{name}{{animation-name:{name}}}")
            defs.append(f'<clipPath id="{name}"><path d="M{x:.1f},{base}h{WIDE}l{DEEP_X},-{DEEP_Y}v-{h}h-{WIDE}l-{DEEP_X},{DEEP_Y}z"/></clipPath>')
            towers.append(
                f'<g clip-path="url(#{name})"><g class="b {name}">'
                f'<path d="M{x:.1f},{base}h{WIDE}v-{h}h-{WIDE}z" fill="{front}"/>'
                f'<rect x="{x:.1f}" y="{base - h}" width="{WIDE}" height="{h}" fill="url(#win{depth})"/>'
                f'<path d="M{x + WIDE:.1f},{base}l{DEEP_X},-{DEEP_Y}v-{h}l-{DEEP_X},{DEEP_Y}z" fill="{side}"/>'
                f'<path d="M{x:.1f},{base - h}h{WIDE}l{DEEP_X},-{DEEP_Y}h-{WIDE}z" fill="{top}"/></g></g>')
            if starts[week] + dt.timedelta(days=weekday) == peak_day:
                count = daily[peak_day]
                css.append(f"@keyframes peak{{0%,{grown + RISE:.2f}%{{opacity:0}}{grown + RISE + 1:.2f}%,{bite - 0.3:.2f}%{{opacity:1}}"
                           f"{bite:.2f}%,100%{{opacity:0}}}}.peak{{animation-name:peak}}")
                peak = (f'<g class="peak">{text(x + WIDE / 2 + 3, base - h - DEEP_Y - 8, f"{count} contributions in a day", 11, t["ink2"], 600, "middle")}</g>')
    css.append("@media (prefers-reduced-motion:reduce){.b,.peak{animation:none}.pac,.ghost{display:none}}")
    if freeze is not None:
        css.append(f".b,.pac,.peak,.jl,.jr{{animation-delay:-{freeze}s}}.b,.pac,.peak,.jl,.jr,.ghost,.float{{animation-play-state:paused}}")

    span = weeks * SLOT
    back = 6 * BACK_X + DEEP_X
    rise = 6 * BACK_Y + DEEP_Y
    plane = (f'<path d="M{left - 8:.1f},{GROUND + 6}h{span + 10}l{back + 8},-{rise + 12}h-{span + 10}z" fill="{t["ground"]}"/>')
    labels = [text(left - 12, GROUND + 5, "Sun", 10, t["muted"], anchor="end"),
              text(left - 12 + 6 * BACK_X, GROUND + 5 - 6 * BACK_Y, "Mon", 10, t["muted"], anchor="end")]
    for week, start in enumerate(starts):
        sunday = start + dt.timedelta(days=6)
        if sunday.day <= 7:
            labels.append(text(left + week * SLOT, GROUND + 24, sunday.strftime("%b"), 11, t["muted"]))
    r = RADIUS
    eater = (f'<g class="pac"><path class="jl" d="M0,-{r}A{r},{r} 0 0 0 0,{r}L0,0Z" fill="url(#ball)"/>'
             f'<path class="jr" d="M0,-{r}A{r},{r} 0 0 1 0,{r}L0,0Z" fill="url(#ball)"/></g>')
    ghosts = [f'<g class="ghost g{index}"><g class="float">'
              f'<path d="M-11,10V-2A11,11 0 0 1 11,-2V10l-3.67,-4l-3.67,4l-3.66,-4l-3.67,4l-3.66,-4z" fill="url(#g{index})"/>'
              '<ellipse cx="-3.5" cy="-3" rx="3" ry="3.6" fill="#fff"/><ellipse cx="4.5" cy="-3" rx="3" ry="3.6" fill="#fff"/>'
              '<circle cx="-2.3" cy="-2.6" r="1.6" fill="#1c3fd6"/><circle cx="5.7" cy="-2.6" r="1.6" fill="#1c3fd6"/></g></g>'
              for index in reversed(range(len(GHOSTS)))]
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
        f'aria-label="2026 as a city that builds itself, one tower for each day of contributions, then is eaten tower by tower">',
        f"<style>{''.join(css)}</style>", f'<defs>{"".join(defs)}</defs>',
        f'<rect width="{W}" height="{H}" rx="12" fill="{t["surface"]}"/>',
        text(PAD, 50, f"{peak_day.year}, built day by day", 20, t["ink"], 600),
        text(PAD, 70, f"Each tower is one day of my contributions, with a floor for {every}. Then it all gets eaten, roof first.", 13, t["ink2"]),
        plane, *lots, *towers, peak, *labels, *ghosts, eater, "</svg>"])


def fetch():
    """Rewrite days.json from the contribution calendar for the year so far."""
    today = dt.datetime.now(dt.timezone.utc)
    query = ("query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){contributionsCollection(from:$from,to:$to)"
             "{contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}")
    variables = {"login": os.environ["GITHUB_REPOSITORY_OWNER"], "from": f"{today.year}-01-01T00:00:00Z", "to": today.strftime("%Y-%m-%dT%H:%M:%SZ")}
    request = urllib.request.Request("https://api.github.com/graphql", json.dumps({"query": query, "variables": variables}).encode(),
                                     {"Authorization": "bearer " + os.environ["GITHUB_TOKEN"]})
    with urllib.request.urlopen(request) as response:
        calendar = json.load(response)["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = {day["date"]: day["contributionCount"] for week in calendar["weeks"] for day in week["contributionDays"]}
    if not any(days.values()):
        return  # nothing yet this year: keep last year's city until there is something to build
    with open(os.path.join(ROOT, "days.json"), "w", encoding="utf-8") as handle:
        json.dump(days, handle, indent=0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--freeze", type=float)
    args = parser.parse_args()
    if args.fetch:
        fetch()
    with open(os.path.join(ROOT, "days.json"), encoding="utf-8") as handle:
        daily = {dt.date.fromisoformat(day): count for day, count in json.load(handle).items()}
    monday = min(daily) - dt.timedelta(days=min(daily).weekday())
    starts = [monday + dt.timedelta(days=7 * week) for week in range((max(daily) - monday).days // 7 + 1)]
    suffix = "" if args.freeze is None else f"-at{args.freeze:g}"
    for name, theme in THEMES.items():
        with open(os.path.join(ROOT, f"city-{name}{suffix}.svg"), "w", encoding="utf-8") as handle:
            handle.write(draw(daily, starts, theme, args.freeze))


if __name__ == "__main__":
    main()
