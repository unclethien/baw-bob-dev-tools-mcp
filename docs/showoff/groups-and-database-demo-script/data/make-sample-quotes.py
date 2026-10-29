#!/usr/bin/env python3
"""Write 20 fictional quotes as a CSV that fits the table of the app Bob built, for the demo's spreadsheet step.

    python3 docs/showoff/groups-and-database-demo-script/data/make-sample-quotes.py \
        work/ZZGDB.app.json work/demo-quotes.csv

Reads the app spec Bob wrote (it needs a "database" section) the way create_app does, so the headings are the
table's columns, whatever Bob named the fields. The key gets made-up company names; a choice gets one of its own
options (never "Other"); a yes/no, number or date gets a plausible value; other text stays empty. The same spec
always gives the same file. The rows are invented: the file is test data and stays in work/.
"""
import csv
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "server"))
import generate_app  # noqa: E402

GROUPS = ["Northwind Logistics", "Bluebird Dental Partners", "Cedar Ridge Schools", "Harbor Point Hotels",
          "Riverbend Credit Union", "Granite Peak Construction", "Pinecrest Software", "Silver Lake Foods",
          "Ironwood Manufacturing", "Maple Grove Senior Living", "Summit Valley Clinics", "Lakeshore Transit",
          "Redwood Analytics", "Coastal Breeze Resorts", "Prairie Wind Energy", "Oak Hollow Veterinary",
          "Blue Mesa Logistics", "Evergreen Library District", "Copper Canyon Mining", "Sunrise Bakeries"]


def value(column: dict, field: dict, rng: random.Random, row: int) -> str:
    label = (field.get("label") or "").lower()
    if column["key"]:
        return GROUPS[row]
    if column["field"] == generate_app.REFERENCE:
        return f"SAMPLE-{row + 1:04d}"
    options = [o.get("value") if isinstance(o, dict) else o for o in field.get("options") or []]
    options = [o for o in options if str(o).strip().lower() != "other"]
    if options:
        return str(rng.choice(options))
    if column["type"] == "Boolean":
        return rng.choice(["true", "false"])
    if column["type"] == "Date":
        return rng.choice(["2027-01-01", "2027-04-01", "2027-07-01", "2027-10-01"])
    if column["type"] == "Integer":
        return str(rng.choice([26, 26, 26, 30]) if "age" in label else rng.randint(1, 5))
    if column["type"] == "Decimal":
        if "%" in label or "percent" in label:
            return f"{rng.choice(range(20, 65, 5)) / 10:.1f}"
        return str(rng.choice(range(500, 5001, 250)))
    return ""


def main(spec_path: str, dest: str) -> None:
    spec = generate_app.load_spec(Path(spec_path))
    plan = spec.get("_database")
    if not plan:
        raise SystemExit(f"{spec_path} has no database section, so there is no table to fit")
    by_name = {f["name"]: f for f in generate_app.fields(spec)}
    rng = random.Random(plan["table"])
    with open(dest, "w", newline="") as out:
        writer = csv.writer(out)
        writer.writerow([c["column"] for c in plan["columns"]])
        for row in range(len(GROUPS)):
            writer.writerow([value(c, by_name.get(c["field"], {}), rng, row) for c in plan["columns"]])
    table = f"{plan['schema']}.{plan['table']}"
    print(f"Wrote {dest}: {len(GROUPS)} fictional quotes for {table}, {len(plan['columns'])} columns")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
