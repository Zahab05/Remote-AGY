import os
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
from src.watcher.base import BaseSLCMAdapter, AssignmentData

logger = logging.getLogger(__name__)

class SatuUIAdapter(BaseSLCMAdapter):
    """
    Adapter khusus untuk portal Universitas Indonesia (SATU UI / EMAS UI & SSO UI).
    Mendukung otomatisasi login menggunakan Playwright atau pemanfaatan session cookies.
    """
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.sso_url = self.config.get("sso_url", "https://sso.ui.ac.id/cas/login")
        self.portal_url = self.config.get("portal_url", "https://satu.ui.ac.id")
        self.emas_url = self.config.get("emas_url", "https://emas3.ui.ac.id")
        self.session_file = self.config.get("session_file", "config/ui_session.json")
        self.headless = self.config.get("headless", True)
        
        # Ambil kredensial dari environment jika tidak ada di config
        self.username = os.environ.get("UI_SSO_USERNAME") or self.config.get("username", "")
        self.password = os.environ.get("UI_SSO_PASSWORD") or self.config.get("password", "")

    def login(self) -> bool:
        """
        Melakukan login ke SSO UI via Playwright dan menyimpan session cookie.
        """
        if not self.username or not self.password:
            logger.warning("Kredensial SSO UI (UI_SSO_USERNAME / UI_SSO_PASSWORD) belum diisi.")
            return False

        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context()
                page = context.new_page()

                logger.info(f"Membuka halaman SSO UI: {self.sso_url}")
                page.goto(self.sso_url, timeout=30000)

                # Isi form login CAS SSO UI
                if page.locator('input[name="username"]').count() > 0:
                    page.fill('input[name="username"]', self.username)
                    page.fill('input[name="password"]', self.password)
                    page.click('button[type="submit"], input[type="submit"], input[name="submit"]')
                    page.wait_for_load_state("load", timeout=15000)

                # Simpan cookies ke file session
                cookies = context.cookies()
                os.makedirs(os.path.dirname(self.session_file), exist_ok=True)
                with open(self.session_file, "w") as f:
                    json.dump(cookies, f, indent=2)
                
                logger.info(f"Login SSO UI berhasil, session tersimpan di {self.session_file}")
                browser.close()
                return True
        except Exception as e:
            logger.error(f"Gagal login ke SSO UI: {e}")
            return False

    def fetch_active_assignments(self) -> List[AssignmentData]:
        """
        Mengambil daftar tugas aktif dari EMAS UI / SATU UI.
        """
        assignments: List[AssignmentData] = []
        
        # Coba buka via Playwright dengan cookies yang tersimpan
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context()

                # Load cookies jika ada
                if os.path.exists(self.session_file):
                    try:
                        with open(self.session_file, "r") as f:
                            cookies = json.load(f)
                            context.add_cookies(cookies)
                    except Exception as ce:
                        logger.warning(f"Gagal memuat cookies session: {ce}")

                page = context.new_page()
                target_url = f"{self.emas_url}/my/"
                logger.info(f"Mengakses halaman dashboard tugas: {target_url}")
                page.goto(target_url, timeout=30000)

                # Cek apakah ter-redirect ke login SSO
                if "sso.ui.ac.id" in page.url:
                    logger.info("Session kedaluwarsa, mencoba login ulang...")
                    if self.login():
                        # Muat ulang cookies dan buka kembali
                        with open(self.session_file, "r") as f:
                            cookies = json.load(f)
                            context.add_cookies(cookies)
                        page.goto(target_url, timeout=30000)
                    else:
                        browser.close()
                        return assignments

                # Parse tugas dari halaman Moodle EMAS UI (Timeline Block atau Upcoming Events)
                html = page.content()
                soup = BeautifulSoup(html, "html.parser")
                
                # Moodle timeline event selector
                event_elements = soup.select(".timeline-event-list-item, .event, .activityinstance, div[data-region='event-item']")
                for idx, el in enumerate(event_elements):
                    title_elem = el.select_one(".event-name, a.aal_header, .instancename")
                    course_elem = el.select_one(".event-course, .course-name, .text-muted")
                    time_elem = el.select_one(".event-time, .timeline-date, small")
                    
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        course = course_elem.get_text(strip=True) if course_elem else "Universitas Indonesia"
                        due_time = time_elem.get_text(strip=True) if time_elem else "Tidak ada batas waktu"
                        task_link = title_elem.get("href") or ""
                        
                        task_id = f"ui-emas-{hash(title + course) % 1000000}"
                        assignments.append(AssignmentData(
                            id=task_id,
                            portal="ui_satu_emas",
                            course_name=course,
                            title=title,
                            description=f"Tautan tugas: {task_link}\nBatas waktu dari portal: {due_time}",
                            due_date=due_time
                        ))

                browser.close()
        except Exception as e:
            logger.error(f"Terjadi kesalahan saat scraping EMAS UI: {e}")

        return assignments

    def fetch_assignment_details(self, task_id: str) -> Optional[AssignmentData]:
        # Untuk detail lengkap, bisa dibuka langsung halaman tugas spesifik jika ada URL-nya
        return None
