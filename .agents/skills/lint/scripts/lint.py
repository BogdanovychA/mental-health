import argparse
import datetime
import os
import re

# Setup paths relative to the script location
script_dir = os.path.dirname(os.path.abspath(__file__))
# The workspace root is 4 levels up: .agents/skills/lint/scripts/lint.py -> .agents/skills/lint/scripts -> .agents/skills/lint -> .agents/skills -> workspace
workspace_dir = os.path.abspath(os.path.join(script_dir, "../../../.."))
data_dir = os.path.join(workspace_dir, "data")
index_path = os.path.join(data_dir, "index.md")
log_path = os.path.join(data_dir, "log.md")


def normalize_filename(name):
    # Remove extension
    name_no_ext = os.path.splitext(name)[0]
    # Remove non-alphanumeric characters and convert to lowercase
    return re.sub(r'[^a-zA-Z0-9]', '', name_no_ext).lower()


def parse_index():
    if not os.path.exists(index_path):
        return [], []
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract reports
    reports = []
    # Format: | [2025/12/22-W52-report-1](./reports/2025/12/22-W52-report-1.md) | `2025-12-22` — `2025-12-28` | +17 | `...` |
    report_matches = re.findall(
        r'\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|\s*`?([0-9-]{10})`?\s*[—–-]\s*`?([0-9-]{10})`?\s*\|\s*([^|]*)\s*\|\s*([^|]*)\s*\|',
        content,
    )
    for match in report_matches:
        score_str = match[4].strip()
        try:
            # Strip potential leading plus signs
            if score_str.startswith("+"):
                score_str = score_str[1:]
            score = int(score_str) if score_str else 0
        except ValueError:
            score = 0

        # Normalize period to template format with backticks: `YYYY-MM-DD` — `YYYY-MM-DD`
        period = f"`{match[2]}` — `{match[3]}`"
        # Strip any surrounding backticks from the summary so it round-trips cleanly
        summary = match[5].strip().strip("`").strip()

        reports.append(
            {
                "name": match[0].strip(),
                "path": match[1].strip(),
                "period": period,
                "score": score,
                "summary": summary,
            }
        )

    # Extract raw entries
    raws = []
    # Format: | [2025/12/22-inbox-1](./raw/2025/12/22-inbox-1.md) | 2025-12-22 | -3 |
    raw_matches = re.findall(
        r'\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|\s*([0-9-]{10})\s*\|\s*([^|]*)\s*\|',
        content,
    )
    for match in raw_matches:
        score_str = match[3].strip()
        try:
            if score_str.startswith("+"):
                score_str = score_str[1:]
            score = int(score_str) if score_str else 0
        except ValueError:
            score = 0

        raws.append(
            {
                "name": match[0].strip(),
                "path": match[1].strip(),
                "date": match[2].strip(),
                "score": score,
            }
        )

    return raws, reports


def get_disk_files():
    raw_files = []
    report_files = []

    raw_dir = os.path.join(data_dir, "raw")
    reports_dir = os.path.join(data_dir, "reports")

    # Scan raw
    if os.path.exists(raw_dir):
        for root, _, files in os.walk(raw_dir):
            for f in files:
                if f.endswith(".md") and f != ".gitkeep":
                    if "YYYY" in root:
                        continue
                    rel_path = os.path.relpath(os.path.join(root, f), data_dir)
                    raw_files.append(
                        "./" + rel_path if not rel_path.startswith("./") else rel_path
                    )

    # Scan reports
    if os.path.exists(reports_dir):
        for root, _, files in os.walk(reports_dir):
            for f in files:
                if f.endswith(".md") and f != ".gitkeep":
                    if "YYYY" in root:
                        continue
                    rel_path = os.path.relpath(os.path.join(root, f), data_dir)
                    report_files.append(
                        "./" + rel_path if not rel_path.startswith("./") else rel_path
                    )

    return raw_files, report_files


def parse_raw_file(rel_path):
    # Normalize path (remove leading ./ if any)
    p = rel_path.lstrip("./")
    abs_path = os.path.join(data_dir, p)
    if not os.path.exists(abs_path):
        return None

    with open(abs_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse date
    date_match = re.search(r'\*\*Дата джерела\*\*\s*\|\s*([0-9-]{10})', content)
    date_str = date_match.group(1) if date_match else None

    # Parse score from parameters table
    score_match = re.search(r'\*\*Баланс балів\*\*\s*\|\s*([+-]?\d+)', content)
    reported_score = int(score_match.group(1)) if score_match else 0

    # Parse activities table and calculate score sum
    activities_started = False
    score_sum = 0
    for line in content.split("\n"):
        if "## Активності" in line:
            activities_started = True
            continue
        if activities_started and line.strip().startswith("|"):
            if "Активність" in line or "---" in line:
                continue
            parts = [pt.strip() for pt in line.split("|")]
            if len(parts) >= 4:
                score_str = parts[2]
                num_match = re.search(r'([+-]?\d+)', score_str)
                if num_match:
                    score_sum += int(num_match.group(1))

    return {
        "date": date_str,
        "reported_score": reported_score,
        "calculated_score": score_sum,
    }


def parse_report_file(rel_path):
    p = rel_path.lstrip("./")
    abs_path = os.path.join(data_dir, p)
    if not os.path.exists(abs_path):
        return None

    with open(abs_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse period
    period_match = re.search(
        r'\*\*Період\*\*\s*\|\s*`?([0-9-]{10})`?\s*[—–-]\s*`?([0-9-]{10})`?', content
    )
    period_str = (
        f"`{period_match.group(1)}` — `{period_match.group(2)}`"
        if period_match
        else None
    )

    # Parse score
    score_match = re.search(r'\*\*Баланс балів\*\*\s*\|\s*([+-]?\d+)', content)
    reported_score = int(score_match.group(1)) if score_match else 0

    # Parse short conclusion (summary)
    conclusion_match = re.search(r'\*\*Короткий висновок\*\*\s*\|\s*([^|\n]+)', content)
    conclusion = (
        conclusion_match.group(1).strip().strip("`").strip() if conclusion_match else ""
    )

    # Parse sources table
    sources = []
    sources_started = False
    for line in content.split("\n"):
        if "## Джерела (Raw)" in line:
            sources_started = True
            continue
        if sources_started and line.strip().startswith("|"):
            if "Джерело" in line or "---" in line:
                continue
            parts = [pt.strip() for pt in line.split("|")]
            if len(parts) >= 4:
                link_match = re.search(r'\[([^\]]+)\]\(([^)]+)\)', parts[1])
                if link_match:
                    sources.append(
                        {"name": link_match.group(1), "path": link_match.group(2)}
                    )

    return {
        "period": period_str,
        "reported_score": reported_score,
        "summary": conclusion,
        "sources": sources,
    }


def has_data_in_section(content, section_title):
    pattern = rf'{re.escape(section_title)}\n.*?(?=\n---|\Z)'
    match = re.search(pattern, content, flags=re.DOTALL)
    if not match:
        return False
    section_content = match.group(0)
    rows = re.findall(r'\|\s*\[[^\]]+\]\([^)]+\)', section_content)
    return len(rows) > 0


def save_index(raws, reports):
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Safeguard check to prevent accidental data erasure due to parsing issues
    if not raws and has_data_in_section(content, "## Вхідні матеріали (Raw)"):
        raise ValueError(
            "Помилка безпеки: Спроба очистити секцію 'Вхідні матеріали (Raw)', "
            "хоча оригінальний файл містить записи. Можливо, парсер не зміг зчитати дані через зміну формату."
        )
    if not reports and has_data_in_section(content, "## Звіти (Reports)"):
        raise ValueError(
            "Помилка безпеки: Спроба очистити секцію 'Звіти (Reports)', "
            "хоча оригінальний файл містить записи. Можливо, парсер не зміг зчитати дані через зміну формату."
        )

    # We will reconstruct index sections
    # Reports table reconstruction
    reports_header = "## Звіти (Reports)\n\n| Звіт | Період | Баланс балів | Висновок |\n| :--- | :--- | :--- | :--- |\n"
    reports_lines = []
    for r in reports:
        score_str = f"+{r['score']}" if r['score'] > 0 else str(r['score'])
        # Wrap the conclusion in backticks to match templates/index.md format
        summary = r["summary"]
        if not summary.startswith("`"):
            summary = f"`{summary}`"
        reports_lines.append(
            f"| [{r['name']}]({r['path']}) | {r['period']} | {score_str} | {summary} |"
        )
    reports_table = reports_header + "\n".join(reports_lines) + "\n"

    # Raw table reconstruction
    raws_header = "## Вхідні матеріали (Raw)\n\n| Джерело | Дата джерела | Баланс балів |\n| :--- | :--- | :--- |\n"
    raws_lines = []
    for r in raws:
        score_str = f"+{r['score']}" if r['score'] > 0 else str(r['score'])
        raws_lines.append(f"| [{r['name']}]({r['path']}) | {r['date']} | {score_str} |")
    raws_table = raws_header + "\n".join(raws_lines) + "\n"

    # Replace sections in content
    # Find start and end of sections
    # Replace reports section
    content = re.sub(
        r'## Звіти \(Reports\)\n.*?(?=\n---|\Z)',
        reports_table.strip(),
        content,
        flags=re.DOTALL,
    )
    # Replace raws section
    content = re.sub(
        r'## Вхідні матеріали \(Raw\)\n.*?(?=\n---|\Z)',
        raws_table.strip(),
        content,
        flags=re.DOTALL,
    )

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(content)


def run_lint(fix=False):
    raws_idx, reports_idx = parse_index()
    raws_disk, reports_disk = get_disk_files()

    tech_fixes_done = []
    tech_errors_unresolved = []
    gaps_warnings = []

    # 1. Broken links in index
    raws_idx_valid = []
    for r in raws_idx:
        p = r["path"]
        if p not in raws_disk:
            # Check if file exists at another path on disk (typo)
            filename = os.path.basename(p)
            norm_filename = normalize_filename(filename)
            found = False
            for d_path in raws_disk:
                d_filename = os.path.basename(d_path)
                if (
                    d_filename == filename
                    or normalize_filename(d_filename) == norm_filename
                ):
                    if fix:
                        r["path"] = d_path
                        tech_fixes_done.append(
                            f"Виправлено посилання для raw джерела '{r['name']}': змінено шлях на '{d_path}'"
                        )
                    else:
                        tech_errors_unresolved.append(
                            f"Битe посилання: '{p}' не існує, але знайдено файл за шляхом '{d_path}' (рекомендується виправити)"
                        )
                    found = True
                    break
            if not found:
                tech_errors_unresolved.append(
                    f"Битe посилання на raw джерело: '{p}' (файл не знайдено на диску). Видалення заборонено без згоди."
                )
                raws_idx_valid.append(r)  # keep it as per instructions
        else:
            raws_idx_valid.append(r)

    reports_idx_valid = []
    for r in reports_idx:
        p = r["path"]
        if p not in reports_disk:
            filename = os.path.basename(p)
            norm_filename = normalize_filename(filename)
            found = False
            for d_path in reports_disk:
                d_filename = os.path.basename(d_path)
                if (
                    d_filename == filename
                    or normalize_filename(d_filename) == norm_filename
                ):
                    if fix:
                        r["path"] = d_path
                        tech_fixes_done.append(
                            f"Виправлено посилання для звіту '{r['name']}': змінено шлях на '{d_path}'"
                        )
                    else:
                        tech_errors_unresolved.append(
                            f"Битe посилання: '{p}' не існує, але знайдено звіт за шляхом '{d_path}' (рекомендується виправити)"
                        )
                    found = True
                    break
            if not found:
                tech_errors_unresolved.append(
                    f"Битe посилання на звіт: '{p}' (файл не знайдено на диску). Видалення заборонено без згоди."
                )
                reports_idx_valid.append(r)
        else:
            reports_idx_valid.append(r)

    # Update arrays
    raws_idx = raws_idx_valid
    reports_idx = reports_idx_valid

    # Check for duplicate paths in index
    seen_raw_paths = set()
    dup_raw_paths = set()
    raws_idx_unique = []
    for r in raws_idx:
        p = r["path"]
        if p in seen_raw_paths:
            dup_raw_paths.add(p)
            if fix:
                tech_fixes_done.append(
                    f"Видалено дубльований запис для raw джерела '{r['name']}' ({r['path']}) з покажчика"
                )
            else:
                tech_errors_unresolved.append(
                    f"Дубльований запис в покажчику для raw '{r['name']}' ({r['path']})"
                )
        else:
            seen_raw_paths.add(p)
            raws_idx_unique.append(r)

    if fix and dup_raw_paths:
        raws_idx = raws_idx_unique

    seen_report_paths = set()
    dup_report_paths = set()
    reports_idx_unique = []
    for r in reports_idx:
        p = r["path"]
        if p in seen_report_paths:
            dup_report_paths.add(p)
            if fix:
                tech_fixes_done.append(
                    f"Видалено дубльований запис для звіту '{r['name']}' ({r['path']}) з покажчика"
                )
            else:
                tech_errors_unresolved.append(
                    f"Дубльований запис в покажчику для звіту '{r['name']}' ({r['path']})"
                )
        else:
            seen_report_paths.add(p)
            reports_idx_unique.append(r)

    if fix and dup_report_paths:
        reports_idx = reports_idx_unique

    # Paths lists for easy check
    raws_idx_paths = [r["path"] for r in raws_idx]
    reports_idx_paths = [r["path"] for r in reports_idx]

    # 2. Orphan files on disk
    for p in raws_disk:
        if p not in raws_idx_paths:
            # Parse file to add to index
            data = parse_raw_file(p)
            if data:
                # Name format: 2026/07/15-inbox-1
                # Remove ./raw/ and .md
                name = p.replace("./raw/", "").replace(".md", "")
                new_entry = {
                    "name": name,
                    "path": p,
                    "date": data["date"] or name.split("-")[0].replace("/", "-"),
                    "score": data["calculated_score"],
                }
                if fix:
                    raws_idx.append(new_entry)
                    tech_fixes_done.append(
                        f"Додано файл-одинак raw джерела '{new_entry['name']}' ({new_entry['path']}) до індексу"
                    )
                else:
                    tech_errors_unresolved.append(
                        f"Файл-одинак на диску (відсутній в індексі): '{p}'"
                    )

    for p in reports_disk:
        if p not in reports_idx_paths:
            data = parse_report_file(p)
            if data:
                name = p.replace("./reports/", "").replace(".md", "")
                new_entry = {
                    "name": name,
                    "path": p,
                    "period": data["period"] or "Невідомий період",
                    "score": data["reported_score"],
                    "summary": data["summary"] or "Немає висновку",
                }
                if fix:
                    reports_idx.append(new_entry)
                    tech_fixes_done.append(
                        f"Додано файл-одинак звіту '{new_entry['name']}' ({new_entry['path']}) до індексу"
                    )
                else:
                    tech_errors_unresolved.append(
                        f"Файл-одинак звіту на диску (відсутній в індексі): '{p}'"
                    )

    # 3. Score mismatches and recalculation
    for r in raws_idx:
        p = r["path"]
        data = parse_raw_file(p)
        if data:
            if data["reported_score"] != r["score"]:
                if fix:
                    tech_fixes_done.append(
                        f"Оновлено баланс балів для raw '{r['name']}' в індексі: з {r['score']} на {data['reported_score']}"
                    )
                    r["score"] = data["reported_score"]
                else:
                    tech_errors_unresolved.append(
                        f"Розбіжність балів raw '{r['name']}': в індексі {r['score']}, у файлі {data['reported_score']}"
                    )
            if data["calculated_score"] != data["reported_score"]:
                tech_errors_unresolved.append(
                    f"Внутрішня помилка балів у файлі '{p}': у параметрах {data['reported_score']}, сума активностей {data['calculated_score']} (потрібно виправити сам файл)"
                )

    for r in reports_idx:
        p = r["path"]
        data = parse_report_file(p)
        if data:
            if data["reported_score"] != r["score"]:
                if fix:
                    tech_fixes_done.append(
                        f"Оновлено баланс балів для звіту '{r['name']}' в індексі: з {r['score']} на {data['reported_score']}"
                    )
                    r["score"] = data["reported_score"]
                else:
                    tech_errors_unresolved.append(
                        f"Розбіжність балів звіту '{r['name']}': в індексі {r['score']}, у файлі {data['reported_score']}"
                    )
            if data["summary"] != r["summary"]:
                if fix:
                    tech_fixes_done.append(
                        f"Оновлено висновок для звіту '{r['name']}' в індексі"
                    )
                    r["summary"] = data["summary"]
                else:
                    tech_errors_unresolved.append(
                        f"Розбіжність висновку звіту '{r['name']}': в покажчику та файлі"
                    )

            # Check sum of raw sources inside report
            raw_sum = 0
            for src in data["sources"]:
                # Resolve relative path: ../../../raw/2025/12/22-inbox-1.md -> ./raw/2025/12/22-inbox-1.md
                src_rel = src["path"].replace("../../../", "./")
                raw_data = parse_raw_file(src_rel)
                if raw_data:
                    raw_sum += raw_data["calculated_score"]
                else:
                    tech_errors_unresolved.append(
                        f"Звіт '{p}' посилається на неіснуюче джерело '{src['path']}'"
                    )

            if raw_sum != data["reported_score"]:
                tech_errors_unresolved.append(
                    f"Невідповідність балів у звіті '{p}': баланс звіту {data['reported_score']}, але сума джерел {raw_sum}"
                )

    # Sorting lists chronologically
    # Raw files sorted by date
    raws_idx.sort(key=lambda x: x["date"])

    # Reports sorted by start date
    def get_report_start_date(rep):
        dates = re.findall(r'[0-9-]{10}', rep["period"])
        if len(dates) == 2:
            return datetime.datetime.strptime(dates[0], "%Y-%m-%d").date()
        return datetime.date.min

    reports_idx.sort(key=get_report_start_date)

    if fix and tech_fixes_done:
        save_index(raws_idx, reports_idx)

    # 4. Report gaps analysis
    sorted_reports_meta = []
    for r in reports_idx:
        dates = re.findall(r'[0-9-]{10}', r["period"])
        if len(dates) == 2:
            sorted_reports_meta.append(
                {
                    "name": r["name"],
                    "start": datetime.datetime.strptime(dates[0], "%Y-%m-%d").date(),
                    "end": datetime.datetime.strptime(dates[1], "%Y-%m-%d").date(),
                    "period_str": r["period"],
                }
            )

    for i in range(len(sorted_reports_meta) - 1):
        curr_rep = sorted_reports_meta[i]
        next_rep = sorted_reports_meta[i + 1]
        expected_start = curr_rep["end"] + datetime.timedelta(days=1)
        if next_rep["start"] > expected_start:
            gap_start = expected_start
            gap_end = next_rep["start"] - datetime.timedelta(days=1)

            # Check for raw files in this gap
            raws_in_gap = []
            for r in raws_idx:
                raw_date = datetime.datetime.strptime(r["date"], "%Y-%m-%d").date()
                if gap_start <= raw_date <= gap_end:
                    raws_in_gap.append(r["name"])

            gap_str = f"{gap_start} — {gap_end}"
            if raws_in_gap:
                gaps_warnings.append(
                    f"Пропущений звіт: період {gap_str} містить {len(raws_in_gap)} raw файлів, але звіт відсутній"
                )
            else:
                gaps_warnings.append(
                    f"Прогалина в даних: період {gap_str} не містить ні raw файлів, ні звітів (користувач неактивний)"
                )

    # 5. Check for raw files within report periods that are not included in the report
    for r in raws_idx:
        raw_date = datetime.datetime.strptime(r["date"], "%Y-%m-%d").date()
        for rep in sorted_reports_meta:
            if rep["start"] <= raw_date <= rep["end"]:
                rep_path = (
                    "./reports/" + rep["name"] + ".md"
                    if not rep["name"].endswith(".md")
                    else "./reports/" + rep["name"]
                )
                rep_data = parse_report_file(rep_path)
                if rep_data:
                    source_names = [src["name"] for src in rep_data["sources"]]
                    if r["name"] not in source_names:
                        gaps_warnings.append(
                            f"Невраховане джерело: файл '{r['name']}' ({r['date']}) потрапляє у звітний період '{rep['period_str']}', але відсутній у списку джерел звіту '{rep['name']}'"
                        )
                break

    # Re-calculate outputs in Ukrainian
    print("=== РЕЗУЛЬТАТИ ПЕРЕВІРКИ БАЗИ ДАНИХ ===")
    print("\n[Технічні виправлення (виконано)]")
    if fix and tech_fixes_done:
        for f in tech_fixes_done:
            print(f"- {f}")
    elif fix:
        print(
            "- Технічних помилок для виправлення не знайдено (або виправлення не потребувалось)"
        )
    else:
        print("- Виправлення не запускалися (запустіть з параметром --fix)")

    print("\n[Технічні помилки (невирішені, потребують ручного втручання)]")
    if tech_errors_unresolved:
        for e in tech_errors_unresolved:
            print(f"- {e}")
    else:
        print("- Невирішених технічних помилок не виявлено")

    print("\n[Логічні прогалини та зауваження (потребують уваги користувача)]")
    if gaps_warnings:
        for w in gaps_warnings:
            print(f"- {w}")
    else:
        print("- Логічних прогалин не виявлено")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Database Integrity Linter")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically fix fixable technical errors in index.md",
    )
    args = parser.parse_args()
    run_lint(fix=args.fix)
