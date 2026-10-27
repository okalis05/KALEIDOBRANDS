"""Homepage campaign selection; supplier imports are not modified."""
from datetime import date, timedelta
from pathlib import Path
from django.conf import settings
from django.utils import timezone

WEEKLY_DIR = "brands/images/hero-weekly"
SEASON_DIR = "brands/images/hero-seasonal"

def weekly_image(today=None):
    today = today or timezone.localdate()
    directory = Path(settings.BASE_DIR) / "brands" / "static" / WEEKLY_DIR
    eligible = []
    if directory.exists():
        for file in directory.iterdir():
            if file.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            try:
                publish = date.fromisoformat(file.stem)
            except ValueError:
                continue
            if publish <= today and publish.weekday() == 0:
                eligible.append((publish, file.name))
    return f"{WEEKLY_DIR}/{max(eligible)[1]}" if eligible else None

CAMPAIGNS = {
    "halloween": ("HALLOWEEN COLLECTION", "Make Your Brand Spooktacular.", "Stand out with creative Halloween promotional merchandise."),
    "thanksgiving": ("THANKSGIVING COLLECTION", "Give Thanks. Make It Memorable.", "Celebrate appreciation with thoughtful branded gifts."),
    "christmas": ("CHRISTMAS GIFTING", "Celebrate the Season in Style.", "Make every holiday gift a memorable brand experience."),
    "new-year": ("NEW YEAR COLLECTION", "New Year. Bold Brand Beginnings.", "Start the year with fresh ideas and lasting impressions."),
    "winter": ("WINTER COLLECTION", "Warm Up Your Brand.", "Discover promotional essentials for colder days."),
    "valentines": ("VALENTINE'S DAY", "Share the Love. Grow Your Brand.", "Create meaningful connections with branded gifts."),
    "st-patricks": ("ST. PATRICK'S DAY", "Make Your Brand Shine.", "Bring fresh energy to your promotional campaigns."),
    "spring": ("SPRING COLLECTION", "Fresh Season. Fresh Impressions.", "Refresh your branding with spring essentials."),
    "easter": ("EASTER COLLECTION", "Bright Ideas for Spring.", "Celebrate the season with colorful branded merchandise."),
    "summer": ("SUMMER COLLECTION", "Make Your Brand Shine.", "Stand out at every summer event."),
    "fall": ("AUTUMN COLLECTION", "Fall Into Memorable Branding.", "Thoughtful merchandise for a new season."),
}

def easter_sunday(year):
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19*a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2*e + 2*i - h - k) % 7
    m = (a + 11*h + 22*l) // 451
    n = h + l - 7*m + 114
    return date(year, n // 31, n % 31 + 1)

def campaign_slug(today):
    month, day = today.month, today.day
    if month == 10: return "halloween"
    if month == 11: return "thanksgiving"
    if month == 12: return "christmas" if day <= 25 else "new-year"
    if month == 1: return "new-year" if day <= 7 else "winter"
    if month == 2: return "valentines" if day <= 14 else "winter"
    if month == 3 and day <= 17: return "st-patricks"
    if easter_sunday(today.year) - timedelta(days=14) <= today <= easter_sunday(today.year):
        return "easter"
    if month in (3,4,5): return "spring"
    if month in (6,7,8): return "summer"
    return "fall"

def seasonal_campaign(today=None):
    today = today or timezone.localdate()
    slug = campaign_slug(today)
    label, title, description = CAMPAIGNS[slug]
    directory = Path(settings.BASE_DIR) / "brands" / "static" / SEASON_DIR
    image = next((f"{SEASON_DIR}/{slug}{ext}" for ext in (".webp", ".jpg", ".jpeg", ".png") if (directory / f"{slug}{ext}").is_file()), None)
    return {"label": label, "title": title, "description": description, "image": image}
