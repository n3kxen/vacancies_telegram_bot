# ──────────────────────────────────────────────
# models.py — vacancy data model
# ──────────────────────────────────────────────

from dataclasses import dataclass, asdict


@dataclass
class Vacancy:
    title:       str = ""   # Job title
    company:     str = ""   # Company name
    salary:      str = ""   # Salary (if listed)
    expires:     str = ""   # Expiration date
    url:         str = ""   # Link to the vacancy page
    description: str = ""   # Short description / snippet

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
