"""MagicBricks property-listing scraper.

Collects residential sale listings (title, price, area, location, amenities, etc.)
from MagicBricks search-result pages using Selenium (to render the page) and
BeautifulSoup (to parse it).

Usage:
    python src/scraper.py --cities Pune Mumbai --pages 2

Notes:
    * Requires Google Chrome. Selenium 4.6+ downloads a matching driver
      automatically, so no chromedriver path is needed.
    * Website markup changes over time; the CSS class names below matched the
      site when the data in data/raw/ was collected and may need updating.
    * Scrape politely: keep page counts small, keep the delay between requests,
      and respect the website's terms of use.
"""

import argparse
import random
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

BASE_URL = (
    "https://www.magicbricks.com/property-for-sale/residential-real-estate"
    "?proptype=Multistorey-Apartment,Builder-Floor-Apartment,Penthouse,"
    "Studio-Apartment,Residential-House,Villa&page={page}&cityName={city}"
)

META_FIELDS = {
    "name": "Name",
    "description": "Description",
    "url": "URL",
    "addressLocality": "Address",
    "latitude": "Latitude",
    "longitude": "Longitude",
    "number_of_rooms": "Number of Rooms",
}


class MagicBricksScraper:
    """Scrapes listing cards from MagicBricks search-result pages."""

    def __init__(self, headless: bool = True, delay: tuple = (2, 4)):
        options = Options()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        self.driver = webdriver.Chrome(options=options)
        self.delay = delay
        self.records = []

    def extract(self, cities, pages):
        """Scrape `pages` result pages for every city in `cities`."""
        for city in cities:
            for page in range(1, pages + 1):
                self.driver.get(BASE_URL.format(page=page, city=city))
                time.sleep(random.uniform(*self.delay))
                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                cards = soup.find_all("div", "mb-srp__list")
                before = len(self.records)
                for card in cards:
                    record = self.parse_card(card, city)
                    if record:
                        self.records.append(record)
                print(f"{city} page {page}: {len(self.records) - before} listings")
        return self.records

    @staticmethod
    def parse_card(card, city):
        """Return one listing as a dict, or None if key fields are missing."""
        title = card.find("h2", "mb-srp__card--title")
        price = card.find("div", "mb-srp__card__price--amount")
        if title is None or price is None:
            return None

        society = card.find("a", "mb-srp__card__society--name")
        record = {
            "Property Id": card.get("id"),
            "Title": title.get_text(strip=True),
            "Society Name": society.get_text(strip=True) if society else "",
            "Price": price.get_text(strip=True),
            "City": city,
        }

        for meta in card.find_all("meta"):
            field = META_FIELDS.get(meta.get("itemprop"))
            if field:
                record[field] = meta.get("content", "")

        labels = card.find_all("div", "mb-srp__card__summary--label")
        values = card.find_all("div", "mb-srp__card__summary--value")
        for label, value in zip(labels, values):
            record[label.get_text(strip=True)] = value.get_text(strip=True)
        return record

    def save(self, out_dir="data/raw"):
        out = Path(out_dir) / f"MagicBricks_{datetime.now():%Y-%m-%d_%H-%M}.xlsx"
        out.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(self.records).to_excel(out, index=False)
        print(f"Saved {len(self.records)} listings to {out}")
        return out

    def close(self):
        self.driver.quit()


def main():
    parser = argparse.ArgumentParser(description="Scrape MagicBricks listings")
    parser.add_argument("--cities", nargs="+", default=["Pune"])
    parser.add_argument("--pages", type=int, default=2)
    parser.add_argument("--show-browser", action="store_true")
    args = parser.parse_args()

    scraper = MagicBricksScraper(headless=not args.show_browser)
    try:
        scraper.extract(args.cities, args.pages)
        scraper.save()
    finally:
        scraper.close()


if __name__ == "__main__":
    main()
