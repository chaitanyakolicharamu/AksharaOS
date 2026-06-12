import json
from pathlib import Path

REPORTS_DIR = Path("reports")


def main():
    print()
    print("=" * 90)
    print(
        f"{'DOCUMENT':30}"
        f"{'TOTAL':>10}"
        f"{'KEPT':>10}"
        f"{'REMOVED':>12}"
        f"{'AVG_SCORE':>12}"
    )
    print("=" * 90)

    for report_file in REPORTS_DIR.glob("*/quality_report.json"):
        with open(report_file, "r", encoding="utf-8") as f:
            report = json.load(f)

        print(
            f"{report['document_id']:30}"
            f"{report['total_chunks']:>10}"
            f"{report['kept']:>10}"
            f"{report['removed']:>12}"
            f"{report['average_quality_score']:>12}"
        )

    print("=" * 90)


if __name__ == "__main__":
    main()
