import datetime
import gzip
import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HALLS = {
    "roberts-dining-hall": "Roberts",
    "dana-dining-hall": "Dana",
    "foss-dining-hall": "Foss",
}
MEALS = {"breakfast", "lunch", "dinner"}


def read_json(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 ColbyDining/0.2",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, identity",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        body = res.read()
        if res.headers.get("Content-Encoding", "").lower() == "gzip" or body[:2] == b"\x1f\x8b":
            body = gzip.decompress(body)
        charset = res.headers.get_content_charset() or "utf-8"
        return json.loads(body.decode(charset))


def menu_urls(hall, meal, date):
    dt = datetime.date.fromisoformat(date)
    y, m, d = dt.year, dt.month, dt.day
    return [
        f"https://colby.api.nutrislice.com/menu/api/weeks/school/{hall}/menu-type/{meal}/{y}/{m}/{d}/?format=json",
        f"https://colby.nutrislice.com/menu/api/weeks/school/{hall}/menu-type/{meal}/{y}/{m}/{d}/?format=json",
    ]


def food_icons(food):
    icons = (((food or {}).get("icons") or {}).get("food_icons") or [])
    return [
        {
            "name": icon.get("name") or icon.get("synced_name") or icon.get("_synced_name"),
            "slug": icon.get("slug"),
            "is_allergen": icon.get("behavior") == 1,
            "is_dietary": icon.get("behavior") == 2,
        }
        for icon in icons
    ]


def compact_item(item, station):
    food = item.get("food") or {}
    nutrition = food.get("rounded_nutrition_info") or {}
    serving = food.get("serving_size_info") or {}
    icons = food_icons(food)
    return {
        "station": station,
        "name": food.get("name") or item.get("text"),
        "category": item.get("category") or food.get("food_category") or None,
        "calories": nutrition.get("calories"),
        "protein_g": nutrition.get("g_protein"),
        "serving": {
            "amount": serving.get("serving_size_amount") or item.get("serving_size_amount"),
            "unit": serving.get("serving_size_unit") or item.get("serving_size_unit"),
        },
        "dietary": [icon["name"] for icon in icons if icon.get("is_dietary")],
        "allergens": [icon["name"] for icon in icons if icon.get("is_allergen")],
        "ingredients": food.get("ingredients") or food.get("synced_ingredients") or "",
        "raw": item,
    }


def extract_day(data, date):
    for day in data.get("days", []):
        if day.get("date") == date:
            return day
    return None


def summarize_day(day):
    station = None
    items = []
    holiday_notes = []
    for item in day.get("menu_items", []):
        if item.get("is_holiday") and item.get("text"):
            holiday_notes.append(item["text"])
            continue
        if item.get("is_station_header"):
            station = item.get("text") or item.get("image_alt") or station
            continue
        if item.get("food") or item.get("food_list"):
            compact = compact_item(item, station)
            if compact.get("name"):
                items.append(compact)
    stations = []
    for item in items:
        if item["station"] and item["station"] not in stations:
            stations.append(item["station"])
    return {"items": items, "stations": stations, "holiday_notes": holiday_notes}


def fetch(hall, meal, date):
    if hall not in HALLS or meal not in MEALS:
        raise ValueError("Invalid hall or meal")
    datetime.date.fromisoformat(date)
    errors = []
    for url in menu_urls(hall, meal, date):
        try:
            data = read_json(url)
            day = extract_day(data, date)
            if not day:
                available = [d.get("date") for d in data.get("days", [])]
                return {
                    "hall": HALLS[hall],
                    "hall_id": hall,
                    "meal": meal,
                    "date": date,
                    "source_url": url,
                    "available_dates": available,
                    "items": [],
                    "stations": [],
                    "message": "Requested date was not present in the Nutrislice week payload.",
                    "raw_day": None,
                }
            summary = summarize_day(day)
            message = None
            if not summary["items"] and summary["holiday_notes"]:
                message = "; ".join(summary["holiday_notes"])
            return {
                "hall": HALLS[hall],
                "hall_id": hall,
                "meal": meal,
                "date": date,
                "source_url": url,
                "last_updated": data.get("last_updated"),
                "stations": summary["stations"],
                "items": summary["items"],
                "item_count": len(summary["items"]),
                "holiday_notes": summary["holiday_notes"],
                "message": message,
                "raw_day": day,
            }
        except Exception as e:
            errors.append(f"{url}: {type(e).__name__}: {str(e)[:200]}")
    raise RuntimeError("; ".join(errors))


TOOLS = [
    {
        "name": "get_colby_menu",
        "description": "Fetch live Colby College dining dishes for one hall, meal, and date. Returns the requested day's stations and compact dish records with nutrition, ingredients, dietary tags, allergens, plus raw_day for deeper inspection.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hall": {"type": "string", "enum": list(HALLS)},
                "meal": {"type": "string", "enum": sorted(MEALS)},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["hall", "meal", "date"],
        },
    },
    {
        "name": "get_colby_locations",
        "description": "List available Colby dining locations and meals.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def mcp_result(req):
    method = req.get("method")
    ident = req.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": ident,
            "result": {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "colby-dining", "version": "0.2.0"},
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": ident, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": ident, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = req.get("params") or {}
        args = params.get("arguments") or {}
        try:
            if params.get("name") == "get_colby_locations":
                data = {"locations": HALLS, "meals": sorted(MEALS)}
            elif params.get("name") == "get_colby_menu":
                data = fetch(args.get("hall", ""), args.get("meal", ""), args.get("date", ""))
            else:
                raise ValueError("Unknown tool")
            result = {"content": [{"type": "text", "text": json.dumps(data)}], "structuredContent": data}
        except Exception as e:
            result = {"isError": True, "content": [{"type": "text", "text": str(e)}]}
        return {"jsonrpc": "2.0", "id": ident, "result": result}
    return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": "Method not found"}}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if urlparse(self.path).path != "/mcp":
            return self.reply(404, {"error": "Not found"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size > 200000:
                raise ValueError("Request too large")
            request = json.loads(self.rfile.read(size))
            result = mcp_result(request)
            if result is None:
                self.send_response(202)
                self.end_headers()
                return
            print("MCP_CALL", request.get("method"), flush=True)
            self.reply(200, result)
        except Exception as e:
            self.reply(400, {"error": str(e)})

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/mcp":
            self.send_response(405)
            self.send_header("Allow", "POST")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path == "/health":
            return self.reply(200, {"ok": True, "app": "colby-dining", "version": "0.2.0"})
        if path == "/api/menu":
            query = parse_qs(urlparse(self.path).query)
            hall = query.get("hall", ["roberts-dining-hall"])[0]
            meal = query.get("meal", ["lunch"])[0]
            date = query.get("date", ["2026-10-12"])[0]
            try:
                return self.reply(200, fetch(hall, meal, date))
            except Exception as e:
                return self.reply(502, {"error": str(e)})
        if path in {"/", "/index.html"}:
            with open("colby-bites.html", "rb") as file:
                body = file.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return self.reply(404, {"error": "Not found"})

    def reply(self, status, obj):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    import threading

    def startup_check():
        for hall in HALLS:
            try:
                result = fetch(hall, "lunch", "2026-10-12")
                print(
                    "COLBY_API_TEST_SUCCESS",
                    json.dumps(
                        {
                            "hall": hall,
                            "url": result["source_url"],
                            "item_count": result["item_count"],
                            "message": result.get("message"),
                            "sample": [item["name"] for item in result["items"][:5]],
                        }
                    ),
                    flush=True,
                )
            except Exception as e:
                print("COLBY_API_TEST_FAILURE", hall, repr(e), flush=True)

    threading.Thread(target=startup_check, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "10000"))), Handler).serve_forever()
