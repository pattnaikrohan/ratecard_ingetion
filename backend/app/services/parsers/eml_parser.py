"""
Enhanced EML/MSG Email Parser
- Extracts ALL attachments (Excel, PDF, images), not just the first one
- Supports .xlsx, .xls, .xlsm, .pdf, .png, .jpg, .jpeg, .tiff, .gif
- Routes Excel attachments to appropriate carrier plugin or generic parser
- Routes PDF/image attachments to Azure Document Intelligence
- Falls back to HTML body table extraction for emails with no usable attachments
- Detects link-only emails and attempts to follow download links
- Merges rate rows from all attachments into a single CanonicalRateSheet
"""
import email
import re
import requests
import tempfile
from pathlib import Path
from typing import Optional, List, Tuple
from urllib.parse import unquote, urlparse
from app.services.parsers.base_parser import BaseParser
from app.services.parsers.plugins.maersk_plugin import MaerskPlugin
from app.services.parsers.plugins.one_plugin import ONEPlugin
from app.services.parsers.plugins.msc_plugin import MSCPlugin
from app.services.parsers.plugins.generic_excel_plugin import GenericExcelPlugin
from app.services.parsers.azure_doc_intel import AzureDocumentIntelligenceParser
from app.models.canonical import CanonicalRateSheet, RateRow, JobSummary
from app.core.config import UPLOADS_DIR


class EMLParser(BaseParser):
    def __init__(self):
        self.maersk_plugin = MaerskPlugin()
        self.one_plugin = ONEPlugin()
        self.msc_plugin = MSCPlugin()
        self.generic_plugin = GenericExcelPlugin()
        self.azure_parser = AzureDocumentIntelligenceParser()

    def can_parse(self, file_path: Path, filename: str) -> bool:
        fn = filename.lower()
        return fn.endswith(".eml") or fn.endswith(".msg")

    def parse(self, file_path: Path, job_id: str) -> CanonicalRateSheet:
        with open(file_path, "rb") as f:
            msg = email.message_from_bytes(f.read())

        subject = msg.get("Subject", "") or ""
        sender = msg.get("From", "") or ""
        print(f"[EML Parser] Subject: {subject}")
        print(f"[EML Parser] From: {sender}")

        # Detect carrier from subject/sender
        carrier_scac = self._detect_carrier(subject, sender)

        # ── Phase 1: Extract ALL attachments ──
        excel_attachments: List[Tuple[Path, str]] = []  # (path, clean_filename)
        pdf_image_attachments: List[Tuple[Path, str]] = []

        for part in msg.walk():
            fn = part.get_filename()
            if not fn:
                continue

            clean_fn = fn.replace('\r\n', '').replace('\r', '').replace('\n', '').strip()
            fn_lower = clean_fn.lower()

            # Skip tiny inline images (signatures, logos) — typically < 10KB
            payload = part.get_payload(decode=True)
            if not payload:
                continue

            is_excel = any(fn_lower.endswith(ext) for ext in ['.xlsx', '.xls', '.xlsm'])
            is_pdf = fn_lower.endswith('.pdf')
            # Treat large images (> 20KB) as potential rate card attachments
            # Include .gif as some carriers embed rate cards as large GIFs
            is_rate_image = (
                any(fn_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.tiff', '.gif'])
                and len(payload) > 20000
                and not fn_lower.startswith('image')  # Skip inline signature images named "image001.png" etc.
            )

            if is_excel or is_pdf or is_rate_image:
                save_path = UPLOADS_DIR / f"{job_id}_{clean_fn}"
                with open(save_path, "wb") as out_f:
                    out_f.write(payload)
                print(f"[EML Parser] Extracted attachment: {clean_fn} ({len(payload)} bytes)")

                if is_excel:
                    excel_attachments.append((save_path, clean_fn))
                else:
                    pdf_image_attachments.append((save_path, clean_fn))

        # ── Phase 2: Process ALL attachments and merge results ──
        all_rates: List[RateRow] = []
        all_carriers: List[str] = []
        validity_start = ""
        validity_end = ""
        contract_number = ""

        # Process Excel attachments
        for att_path, att_name in excel_attachments:
            try:
                sheet = self._parse_excel_attachment(att_path, att_name, job_id, carrier_scac)
                if sheet and sheet.rates:
                    # Re-index rows
                    offset = len(all_rates)
                    for r in sheet.rates:
                        r.row_index = offset + r.row_index
                    all_rates.extend(sheet.rates)
                    if sheet.carrier_code and sheet.carrier_code not in all_carriers:
                        all_carriers.append(sheet.carrier_code)
                    if sheet.validity_start and not validity_start:
                        validity_start = sheet.validity_start
                    if sheet.validity_end and not validity_end:
                        validity_end = sheet.validity_end
                    if sheet.contract_number and not contract_number:
                        contract_number = sheet.contract_number
                    print(f"[EML Parser] Excel '{att_name}': {len(sheet.rates)} rate rows")
                else:
                    print(f"[EML Parser] Excel '{att_name}': 0 rate rows (parser returned empty)")
            except Exception as e:
                print(f"[EML Parser] Error parsing Excel attachment '{att_name}': {e}")
                import traceback
                traceback.print_exc()

        # Process PDF/image attachments via Azure DocIntel
        for att_path, att_name in pdf_image_attachments:
            try:
                sheet = self.azure_parser.parse(att_path, job_id)
                if sheet and sheet.rates:
                    offset = len(all_rates)
                    for r in sheet.rates:
                        r.row_index = offset + r.row_index
                        # Override carrier if detected from email
                        if carrier_scac and r.carrier_scac in ("MAEU", "UNKN", ""):
                            r.carrier_scac = carrier_scac
                    all_rates.extend(sheet.rates)
                    if sheet.carrier_code and sheet.carrier_code not in all_carriers:
                        all_carriers.append(sheet.carrier_code)
                    print(f"[EML Parser] PDF/Image '{att_name}': {len(sheet.rates)} rate rows")
            except Exception as e:
                print(f"[EML Parser] Error parsing PDF/Image attachment '{att_name}': {e}")

        # ── Phase 3: If no usable attachments, parse HTML body ──
        body_text = None
        if not all_rates:
            body_text = self._extract_body(msg)
            if body_text:
                # Try HTML table extraction
                sheet = self.msc_plugin.parse_text(body_text, file_path.name, job_id)
                # Override carrier from email detection
                if carrier_scac:
                    sheet.carrier_code = carrier_scac
                    for r in sheet.rates:
                        r.carrier_scac = carrier_scac

                if sheet.rates:
                    all_rates.extend(sheet.rates)
                    if sheet.carrier_code and sheet.carrier_code not in all_carriers:
                        all_carriers.append(sheet.carrier_code)
                    validity_start = sheet.validity_start
                    validity_end = sheet.validity_end
                    print(f"[EML Parser] HTML body: {len(sheet.rates)} rate rows")

        # ── Phase 4: If still no rates, check for download links ──
        if not all_rates:
            if not body_text:
                body_text = self._extract_body(msg)
            if body_text:
                link_rates = self._try_download_link(body_text, job_id, carrier_scac, file_path.name)
                if link_rates:
                    all_rates.extend(link_rates)
                    print(f"[EML Parser] Downloaded link file: {len(link_rates)} rate rows")

        # Build final merged result
        final_carrier = carrier_scac or (all_carriers[0] if all_carriers else "UNKN")

        summary = JobSummary(
            total_rows=len(all_rates),
            carriers_found=all_carriers if all_carriers else [final_carrier],
        )

        print(f"[EML Parser] Total: {len(all_rates)} rate rows from {len(excel_attachments)} Excel + "
              f"{len(pdf_image_attachments)} PDF/Image attachments")

        return CanonicalRateSheet(
            job_id=job_id,
            file_name=file_path.name,
            carrier_code=final_carrier,
            contract_number=contract_number,
            validity_start=validity_start,
            validity_end=validity_end,
            rates=all_rates,
            summary=summary,
        )

    def _parse_excel_attachment(self, att_path: Path, att_name: str, job_id: str, email_carrier: str) -> Optional[CanonicalRateSheet]:
        """Route an Excel attachment to the best plugin with automatic fallback to generic parser."""
        sheet = None
        if self.maersk_plugin.can_parse(att_path, att_name):
            sheet = self.maersk_plugin.parse(att_path, job_id)
        elif self.one_plugin.can_parse(att_path, att_name):
            sheet = self.one_plugin.parse(att_path, job_id)

        # Fallback to generic intelligent parser if carrier plugin failed or returned 0 rows
        if not sheet or not sheet.rates:
            sheet = self.generic_plugin.parse(att_path, job_id)

        # Override carrier from email context if generic couldn't detect it
        if sheet and email_carrier and sheet.carrier_code in ("UNKN", ""):
            sheet.carrier_code = email_carrier
            for r in sheet.rates:
                if r.carrier_scac in ("UNKN", ""):
                    r.carrier_scac = email_carrier
        return sheet

    def _try_download_link(self, body_text: str, job_id: str, carrier_scac: str, original_filename: str) -> List[RateRow]:
        """
        Detect and follow download links in email body.
        Handles Proofpoint URL defense wrapping, Mailchimp links, and direct file URLs.
        """
        import html
        clean_body = html.unescape(body_text)

        # Extract all URLs from HTML
        urls = re.findall(r'href=["\']?(https?://[^\s"\'<>]+)', clean_body, re.IGNORECASE)
        if not urls:
            urls = re.findall(r'https?://[^\s<>"\']+', clean_body)

        # Filter out obvious non-tariff URLs
        skip_patterns = [
            'unsubscribe', 'profile', 'preferences', 'privacy', 'terms',
            'facebook', 'twitter', 'linkedin', 'instagram', 'youtube',
            'fonts.googleapis', 'fonts.gstatic', 'google-analytics',
            'proofpointessentials.com/email-details',
        ]

        candidate_urls = []
        for url in urls:
            url_clean = url.rstrip('>').rstrip("'").rstrip('"')
            url_lower = url_clean.lower()

            if any(skip in url_lower for skip in skip_patterns):
                continue

            # Proofpoint URL defense — unwrap the real URL
            if 'urldefense.proofpoint.com' in url_lower:
                real_url = self._unwrap_proofpoint(url_clean)
                if real_url:
                    url_clean = real_url
                    url_lower = url_clean.lower()

            # Check if it looks like a tariff/rate link
            is_tariff_link = any(kw in url_lower for kw in [
                'tariff', 'rate', 'lcl', 'fcl', 'freight', 'download',
                'list-manage.com', 'mailchimp', '.xlsx', '.xls', '.pdf', '.xlsm',
            ])

            if is_tariff_link and url_clean not in candidate_urls:
                candidate_urls.append(url_clean)

        if not candidate_urls:
            print(f"[EML Parser] No downloadable tariff links found in email body")
            return []

        # Try each candidate URL
        for url in candidate_urls[:5]:  # Limit to first 5 candidates
            try:
                print(f"[EML Parser] Attempting to download tariff from: {url[:100]}...")
                
                # Use cloudscraper to bypass basic bot protection (Cloudflare/Mailchimp)
                import cloudscraper
                from bs4 import BeautifulSoup
                
                scraper = cloudscraper.create_scraper(browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'desktop': True
                })
                
                resp = scraper.get(url, timeout=30, allow_redirects=True)
                
                # Check for meta redirect in HTML response
                if 'text/html' in resp.headers.get('Content-Type', '').lower() and resp.status_code == 200:
                    soup = BeautifulSoup(resp.content, "html.parser")
                    meta_refresh = soup.find('meta', attrs={'http-equiv': lambda x: x and x.lower() == 'refresh'})
                    if meta_refresh:
                        content = meta_refresh.get('content', '')
                        if 'url=' in content.lower():
                            redirect_url = re.search(r'url=(.*)', content, flags=re.IGNORECASE).group(1).strip("'\"")
                            if not redirect_url.startswith('http'):
                                redirect_url = urlparse(resp.url).scheme + '://' + urlparse(resp.url).netloc + redirect_url
                            print(f"[EML Parser] Following meta redirect to: {redirect_url[:100]}...")
                            resp = scraper.get(redirect_url, timeout=30, allow_redirects=True)

                if resp.status_code != 200:
                    print(f"[EML Parser] Download failed: HTTP {resp.status_code}")
                    continue

                content_type = resp.headers.get('Content-Type', '').lower()
                content_disp = resp.headers.get('Content-Disposition', '')
                final_url = resp.url.lower()

                # Check if response is a downloadable file
                is_file = (
                    'spreadsheet' in content_type or
                    'excel' in content_type or
                    'octet-stream' in content_type or
                    'pdf' in content_type or
                    '.xlsx' in content_disp or '.xls' in content_disp or
                    '.pdf' in content_disp or '.xlsm' in content_disp or
                    '.xlsx' in final_url or '.xls' in final_url or '.pdf' in final_url
                )

                if is_file and len(resp.content) > 1000:
                    # Determine filename from Content-Disposition or final URL
                    dl_filename = "downloaded_tariff.xlsx"
                    if content_disp:
                        fn_match = re.search(r'filename[*]?=["\']?([^"\';\n]+)', content_disp)
                        if fn_match:
                            dl_filename = fn_match.group(1).strip()
                    else:
                        parsed = urlparse(resp.url)
                        if parsed.path and len(Path(parsed.path).name) > 3:
                            dl_filename = Path(parsed.path).name

                    # Save downloaded file
                    save_path = UPLOADS_DIR / f"{job_id}_link_{dl_filename}"
                    with open(save_path, "wb") as f:
                        f.write(resp.content)
                    print(f"[EML Parser] Downloaded: {dl_filename} ({len(resp.content)} bytes)")

                    # Parse the downloaded file
                    fn_lower = dl_filename.lower()
                    sheet = None
                    if fn_lower.endswith('.xlsx') or fn_lower.endswith('.xls') or fn_lower.endswith('.xlsm'):
                        sheet = self._parse_excel_attachment(save_path, dl_filename, job_id, carrier_scac)
                    elif fn_lower.endswith('.pdf'):
                        sheet = self.azure_parser.parse(save_path, job_id)

                    if sheet and sheet.rates:
                        print(f"[EML Parser] Downloaded file yielded {len(sheet.rates)} rate rows")
                        return sheet.rates
                else:
                    # Response might be an HTML page with the tariff embedded
                    if 'text/html' in content_type and len(resp.text) > 500:
                        sheet = self.msc_plugin.parse_text(resp.text, original_filename, job_id)
                        if carrier_scac:
                            sheet.carrier_code = carrier_scac
                            for r in sheet.rates:
                                r.carrier_scac = carrier_scac
                        if sheet.rates:
                            print(f"[EML Parser] Downloaded HTML page yielded {len(sheet.rates)} rate rows")
                            return sheet.rates

            except Exception as e:
                print(f"[EML Parser] Error downloading from {url[:80]}: {e}")
                continue

        return []

    def _unwrap_proofpoint(self, url: str) -> Optional[str]:
        """Unwrap a Proofpoint URL Defense wrapped URL."""
        import html
        url = html.unescape(url)
        match = re.search(r'[?&]u=([^&]+)', url)
        if match:
            encoded = match.group(1)
            decoded = (
                encoded.replace('https-3A__', 'https://')
                       .replace('http-3A__', 'http://')
                       .replace('-3A', ':')
                       .replace('-2F', '/')
                       .replace('-2D', '-')
                       .replace('-26', '&')
                       .replace('-3D', '=')
                       .replace('-3F', '?')
                       .replace('-5F', '_')
                       .replace('-2E', '.')
                       .replace('-25', '%')
                       .replace('-23', '#')
                       .replace('-40', '@')
                       .replace('-2B', '+')
                       .replace('-27', "'")
                       .replace('-7E', '~')
                       .replace('_', '/')
            )
            return decoded
        return None

    def _detect_carrier(self, subject: str, sender: str) -> str:
        """Detect carrier SCAC from email subject and sender."""
        text = (subject + " " + sender).lower()
        carriers = [
            ("MAEU", ["maersk", "maeu", "sealand"]),
            ("ONEY", ["one-line.com", "one ", "oney", "ocean network"]),
            ("MSCU", ["msc.com", "msc ", "mscu"]),
            ("HMMU", ["hmm21.com", "hmm ", "hyundai"]),
            ("ZIMU", ["zim.com", "zim "]),
            ("OOLU", ["oocl.com", "oocl", "orient overseas"]),
            ("CMDU", ["cma-cgm.com", "cma cgm", "cma-cgm", " anl ", "anl-"]),
            ("COSU", ["cosco"]),
            ("EGLV", ["evergreen"]),
            ("HLCU", ["hapag", "hapag-lloyd"]),
            ("YMLU", ["yang ming"]),
            ("AAXU", ["aax "]),
            ("CTLU", ["carotrans", "caro trans"]),
            ("AAWU", ["aaw "]),
            ("VGLU", ["vanguard", "shipco"]),
        ]
        for scac, patterns in carriers:
            for pat in patterns:
                if pat in text:
                    return scac
        return ""

    def _extract_body(self, msg) -> str:
        """Extract full text+HTML body from email message."""
        body = ""
        for part in msg.walk():
            ct = part.get_content_type()
            if ct in ["text/plain", "text/html"]:
                payload = part.get_payload(decode=True)
                if payload:
                    body += payload.decode("utf-8", errors="replace") + "\n"
        return body
