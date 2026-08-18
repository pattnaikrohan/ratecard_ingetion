import sys, email, re

f = open(r'D:\Rate File Template\Rate_File_Template_Completion_Freightify\RE_ Tariff Examples\CaroTrans LCL Export Tariff - 1st-14th August 2026.eml', 'rb')
msg = email.message_from_bytes(f.read())
body = ""
for p in msg.walk():
    if p.get_content_type() in ['text/plain', 'text/html'] and p.get_payload(decode=True):
        body += p.get_payload(decode=True).decode('utf-8', errors='replace')

urls = re.findall(r'href=["\']?(https?://[^\s"\'<>]+)', body, re.IGNORECASE)
print(f"Found {len(urls)} href URLs:")
for u in urls:
    print(" -", u)
