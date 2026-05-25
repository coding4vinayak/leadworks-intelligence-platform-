"""Scraping engine - modular scrapers for lead generation."""
from backend.services.scrapers.base import BaseScraper, ScraperResult
from backend.services.scrapers.website_scraper import WebsiteScraper
from backend.services.scrapers.linkedin_scraper import LinkedInScraper
from backend.services.scrapers.google_maps_scraper import GoogleMapsScraper
from backend.services.scrapers.email_finder import EmailFinder
from backend.services.scrapers.tech_stack_scraper import TechStackScraper
from backend.services.scrapers.social_scraper import SocialMediaScraper
from backend.services.scrapers.scraper_manager import ScraperManager

__all__ = [
    "BaseScraper", "ScraperResult",
    "WebsiteScraper", "LinkedInScraper", "GoogleMapsScraper",
    "EmailFinder", "TechStackScraper", "SocialMediaScraper",
    "ScraperManager",
]
