from datetime import datetime, timezone
from pathlib import Path
import csv
import json


root = Path(__file__).resolve().parent
output_path = root / "library.json"


def parse_time(value):
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def count_csv_rows(path):
    if not path.exists():
        return None
    with open(path, newline="", encoding="utf-8-sig") as file:
        return max(0, sum(1 for _ in file) - 1)


def read_time_range_duration(path):
    if not path.exists():
        return None

    with open(path, newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if "time" not in (reader.fieldnames or []):
            return None

        first_time = None
        last_time = None
        for row in reader:
            row_time = parse_time(row.get("time"))
            if row_time is None:
                continue
            if first_time is None:
                first_time = row_time
            last_time = row_time

    if first_time is None or last_time is None:
        return None
    return (last_time - first_time).total_seconds()


def recommend_playbackrate(duration, nb_rows, max_playback_duration_s=300, reference_bpm=120):
    if nb_rows in (None, 0):
        return None

    reference_rows_per_s = reference_bpm / 60
    reference_duration_s = nb_rows / reference_rows_per_s

    if duration is None:
        playback_duration_s = min(reference_duration_s, max_playback_duration_s)
        return nb_rows / playback_duration_s

    playback_duration_s = max(max_playback_duration_s, reference_duration_s)
    return duration / playback_duration_s


def read_tags(signal_folder):
    tags_path = signal_folder / "tags.json"
    if not tags_path.exists():
        return []

    with open(tags_path, encoding="utf-8") as file:
        tags = json.load(file).get("tags", [])

    if not isinstance(tags, list):
        return []
    return tags


signals = []

for parameters_path in sorted(root.glob("*/*/parameters.json")):
    signal_folder = parameters_path.parent
    category_folder = signal_folder.parent
    category = category_folder.name
    name = signal_folder.name

    # if "template" in category or "template" in name:
    #     continue

    with open(parameters_path, encoding="utf-8") as file:
        params = json.load(file)

    signal_path = signal_folder / params.get("signal_path", "signal.csv")
    range_min = params.get("range_min")
    range_max = params.get("range_max")

    duration = None
    range_min_time = parse_time(range_min)
    range_max_time = parse_time(range_max)
    if range_min_time is not None and range_max_time is not None:
        duration = (range_max_time - range_min_time).total_seconds()
    elif range_min is None and range_max is None:
        duration = read_time_range_duration(signal_path)

    nb_rows = count_csv_rows(signal_path)

    signals.append({
        "name": name,
        "category": category,
        "duration": duration,
        "nb_rows": nb_rows,
        "tags": read_tags(signal_folder),
        "recommended_playbackrate": recommend_playbackrate(duration, nb_rows),
    })


payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "signals": signals,
}

with open(output_path, "w", encoding="utf-8") as file:
    json.dump(payload, file, indent=2, ensure_ascii=False)
    file.write("\n")

print(f"Saved {len(signals)} signals to {output_path.name}")
