# ──────────────────────────────────────────────
# models.py — vacancy data model
# ──────────────────────────────────────────────

from dataclasses import dataclass, asdict


@dataclass
class Vacancy:
    title:       str = ""   # Job title
    company:     str = ""   # Company name
    salary:      str = ""   # Salary (if listed)
    expires:     str = ""   # Raw expiry label from site (e.g. "Beidzas: 22.06.2026"), if any
    url:         str = ""   # Link to the vacancy page
    description: str = ""   # Short description / snippet
    added_date:  str = ""   # ISO date (YYYY-MM-DD) when first stored in vacancies.json
    expiry_date: str = ""   # ISO date when the vacancy should be removed.
                             # Empty => 3 weeks after added_date (default lifetime).

    def to_dict(self) -> dict:
        return asdict(self)

    def short(self) -> str:
        """One-line summary for terminal output."""
        salary = f"  💰 {self.salary}" if self.salary else ""
        return (
            f"🏢 {self.title} | {self.company}\n"
            f"   {salary}\n"
            f"   🔗 {self.url}"
        )
