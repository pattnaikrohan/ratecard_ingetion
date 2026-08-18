import sys, email, re
sys.stdout.reconfigure(encoding='utf-8')
f = open(r'D:\Rate File Template\Rate_File_Template_Completion_Freightify\RE_ Tariff Examples\CaroTrans LCL Export Tariff - 1st-14th August 2026.eml', 'rb')
msg = email.message_from_bytes(f.read())

body = ""
for part in msg.walk():
    ct = part.get_content_type()
    if ct in ["text/plain", "text/html"]:
        payload = part.get_payload(decode=True)
        if payload:
            body += payload.decode("utf-8", errors="replace") + "\n"

# Find all URLs in body
urls = re.findall(r'https?://[^\s<>"\']+', body)
print(f"Found {len(urls)} URLs in email body:\n")
for i, url in enumerate(urls):
    # Clean URL
    url = url.rstrip('>')
    print(f"  [{i+1}] {url[:200]}")

# Also look for link text patterns
link_patterns = re.findall(r'(?:click|download|tariff|lcl).*?(?:https?://[^\s<>"\']+)', body, re.IGNORECASE | re.DOTALL)
print(f"\nLink-context patterns found: {len(link_patterns)}")
for p in link_patterns[:5]:
    clean = re.sub(r'<[^>]+>', ' ', p)
    clean = re.sub(r'\s+', ' ', clean).strip()
    print(f"  Context: {clean[:300]}")
