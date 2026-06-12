from pathlib import Path
import json
import re
from collections import Counter


class QualityProcessor:
    def __init__(self, input_file: str, output_file: str):
        self.input_file = Path(input_file)
        self.output_file = Path(output_file)

        self.document_id = self.input_file.parts[2]
        self.report_dir = Path("reports") / self.document_id
        self.report_file = self.report_dir / "quality_report.json"
        self.removed_file = self.report_dir / "removed_chunks.jsonl"

    def telugu_ratio(self, text: str) -> float:
        telugu_chars = re.findall(r"[\u0C00-\u0C7F]", text)
        useful_chars = re.findall(r"[\u0C00-\u0C7Fa-zA-Z0-9]", text)

        if not useful_chars:
            return 0.0

        return len(telugu_chars) / len(useful_chars)

    def digit_ratio(self, text: str) -> float:
        useful_chars = re.findall(r"[\u0C00-\u0C7Fa-zA-Z0-9]", text)
        digits = re.findall(r"[0-9౦-౯]", text)

        if not useful_chars:
            return 0.0

        return len(digits) / len(useful_chars)

    def telugu_word_count(self, text: str) -> int:
        words = re.findall(r"[\u0C00-\u0C7F]{2,}", text)
        return len(words)

    def is_index_chunk(self, text: str) -> bool:
        index_patterns = [
            r".+\s+\d{2,4}(,\s*\d{2,4})+",
            r"^\d+\s*$",
        ]
        return any(re.search(pattern, text) for pattern in index_patterns)

    def run(self):
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)

        kept = []
        removed = []

        with open(self.input_file, "r", encoding="utf-8") as file:
            chunks = [json.loads(line) for line in file]

        text_counter = Counter(chunk["text"] for chunk in chunks)

        for chunk in chunks:
            text = chunk["text"].strip()

            telugu_ratio = self.telugu_ratio(text)
            digit_ratio = self.digit_ratio(text)
            telugu_words = self.telugu_word_count(text)

            reason = None

            if len(text) < 80:
                reason = "too_short"
            elif text_counter[text] > 1:
                reason = "duplicate"
            elif self.is_index_chunk(text):
                reason = "index_chunk"
            elif digit_ratio > 0.30:
                reason = "numeric_junk"
            elif telugu_words < 8:
                reason = "too_few_telugu_words"
            elif telugu_ratio < 0.50:
                reason = "low_telugu_ratio"

            chunk["quality_score"] = round(telugu_ratio, 3)

            if reason:
                chunk["removed_reason"] = reason
                removed.append(chunk)
            else:
                kept.append(chunk)

        with open(self.output_file, "w", encoding="utf-8") as file:
            for chunk in kept:
                file.write(json.dumps(chunk, ensure_ascii=False) + "\n")

        with open(self.removed_file, "w", encoding="utf-8") as file:
            for chunk in removed:
                file.write(json.dumps(chunk, ensure_ascii=False) + "\n")

        reason_counts = Counter(chunk["removed_reason"] for chunk in removed)

        report = {
            "document_id": self.document_id,
            "input_file": str(self.input_file),
            "output_file": str(self.output_file),
            "total_chunks": len(chunks),
            "kept": len(kept),
            "removed": len(removed),
            "removed_reasons": dict(reason_counts),
            "average_quality_score": (
                round(sum(chunk["quality_score"] for chunk in kept) / len(kept), 3)
                if kept
                else 0
            ),
            "sample_kept": kept[:5],
            "sample_removed": removed[:5],
        }

        with open(self.report_file, "w", encoding="utf-8") as file:
            json.dump(report, file, ensure_ascii=False, indent=2)

        print(f"[QUALITY] Kept: {len(kept)}")
        print(f"[QUALITY] Removed: {len(removed)}")
        print(f"[REPORT] {self.report_file}")
        print(f"[REMOVED] {self.removed_file}")
