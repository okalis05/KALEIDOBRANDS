"""Homepage campaign selection. No supplier import commands are changed."""
from datetime import date
from pathlib import Path
from django.conf import settings
from django.utils import timezone

# Upload a licensed, KaleidoBrands-branded image to the weekly folder.
# Name it YYYY-MM-DD.jpg/png/webp using the Monday it should first appear.
# The most recent eligible date stays active until a newer dated file is added.
WEEKLY_DIR = "brands/images/hero-weekly"
SEASON_DIR = "brands/images/hero-seasonal"

def weekly_image(today=None):
    today = today or timezone.localdate()
    directory = Path(settings.BASE_DIR) / 'brands' / 'static' / WEEKLY_DIR
    eligible = []
    for file in directory.glob('*') if directory.exists() else []:
        if file.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp'}:
            continue
        try:
            publish = date.fromisoformat(file.stem)
        except ValueError:
            continue
        if publish <= today and publish.weekday() == 0:
            eligible.append((publish, file.name))
    return f"{WEEKLY_DIR}/{max(eligible)[1]}" if eligible else None

SEASONS = {
    1: ('WINTER & NEW YEAR', 'Fresh Starts. Lasting Impressions.', 'Start the year with memorable branded merchandise.', 'winter'),
    2: ('WINTER & NEW YEAR', 'Fresh Starts. Lasting Impressions.', 'Start the year with memorable branded merchandise.', 'winter'),
    3: ('SPRING CAMPAIGN', 'Fresh Season. Fresh Impressions.', 'Refresh your branding with inspired spring essentials.', 'spring'),
    4: ('SPRING CAMPAIGN', 'Fresh Season. Fresh Impressions.', 'Refresh your branding with inspired spring essentials.', 'spring'),
    5: ('SPRING CAMPAIGN', 'Fresh Season. Fresh Impressions.', 'Refresh your branding with inspired spring essentials.', 'spring'),
    6: ('SUMMER CAMPAIGN', 'Make Your Brand Shine.', 'Stand out at every summer event.', 'summer'),
    7: ('SUMMER CAMPAIGN', 'Make Your Brand Shine.', 'Stand out at every summer event.', 'summer'),
    8: ('SUMMER CAMPAIGN', 'Make Your Brand Shine.', 'Stand out at every summer event.', 'summer'),
    9: ('AUTUMN CAMPAIGN', 'Fall Into Memorable Branding.', 'Thoughtful merchandise for a new season.', 'fall'),
    10: ('AUTUMN CAMPAIGN', 'Fall Into Memorable Branding.', 'Thoughtful merchandise for a new season.', 'fall'),
    11: ('THANKSGIVING CAMPAIGN', 'Give Thanks. Make It Memorable.', 'Celebrate appreciation with branded gifts.', 'thanksgiving'),
    12: ('HOLIDAY GIFTING', 'Celebrate the Season in Style.', 'Make every holiday gift memorable.', 'holiday'),
}

def seasonal_campaign(today=None):
    today = today or timezone.localdate()
    label, title, description, slug = SEASONS[today.month]
    directory = Path(settings.BASE_DIR) / 'brands' / 'static' / 'brands' / 'images' / 'hero-seasonal'
    image = next((f'{SEASON_DIR}/{slug}{ext}' for ext in ('.webp', '.jpg', '.jpeg', '.png') if (directory / (slug+ext)).is_file()), None)
    return {'label': label, 'title': title, 'description': description, 'image': image}
