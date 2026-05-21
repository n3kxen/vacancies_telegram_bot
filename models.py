# ──────────────────────────────────────────────
# models.py — vacancy data model
# ──────────────────────────────────────────────

from dataclasses import dataclass, asdict


@dataclass
class Vacancy:
    title:       str = ""   # Job title
    company:     str = ""   # Company name
    location:    str = ""   # City / region
    salary:      str = ""   # Salary (if listed)
    url:         str = ""   # Link to the vacancy page
    description: str = ""   # Full vacancy description text

    def to_dict(self) -> dict:
        return asdict(self)

    def short(self) -> str:
        """One-line summary for terminal output."""
        salary = f"  💰 {self.salary}" if self.salary else ""
        return (
            f"🏢 {self.title} | {self.company}\n"
            f"   📍 {self.location}{salary}\n"
            f"   🔗 {self.url}"
        )
