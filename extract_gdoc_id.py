import re, sys

with open('/tmp/njud_1947.gdoc', 'rb') as f:
    content = f.read(5000)

print("=== Primeiros 500 bytes ===")
print(content[:500])
print()

text = content.decode('utf-8', errors='ignore')

# Procurar documentId
m1 = re.findall(r'documentId["\s:]+["\']([a-zA-Z0-9-_]+)', text)
print("=== documentId ===", m1[:3])

# Procurar /d/ pattern
m2 = re.findall(r'/d/([a-zA-Z0-9-_]+)', text)
print("=== /d/ pattern ===", m2[:3])

# Procurar qualquer ID 44-char
m3 = re.findall(r'["\']([a-zA-Z0-9_-]{44})["\']', text)
print("=== 44-char IDs ===", m3[:3])
