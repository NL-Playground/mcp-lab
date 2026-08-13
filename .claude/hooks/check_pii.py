#!/usr/bin/env python3
"""UserPromptSubmit hook: reject prompts that contain likely PII.

Reads the hook JSON payload (with a "prompt" field) from stdin, scans the
prompt text for email addresses, phone numbers, Taiwan National ID numbers,
and credit card numbers, and blocks the prompt if any are found.
"""
import json
import re
import sys

TWID_LETTER_VALUES = {
    "A": 10, "B": 11, "C": 12, "D": 13, "E": 14, "F": 15, "G": 16, "H": 17,
    "I": 34, "J": 18, "K": 19, "L": 20, "M": 21, "N": 22, "O": 35, "P": 23,
    "Q": 24, "R": 25, "S": 26, "T": 27, "U": 28, "V": 29, "W": 32, "X": 30,
    "Y": 31, "Z": 33,
}
TWID_WEIGHTS = [1, 9, 8, 7, 6, 5, 4, 3, 2, 1, 1]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
TWID_RE = re.compile(r"\b[A-Za-z][12]\d{8}\b")
CC_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
PHONE_RE = re.compile(
    r"(?:\+?886[-\s]?9\d{8}\b|\b09\d{2}[-\s]?\d{3}[-\s]?\d{3}\b|\b0\d[-\s]?\d{3,4}[-\s]?\d{4}\b)"
)


def twid_valid(twid: str) -> bool:
    twid = twid.upper()
    if not re.match(r"^[A-Z][12]\d{8}$", twid):
        return False
    n = TWID_LETTER_VALUES.get(twid[0])
    if n is None:
        return False
    digits = [n // 10, n % 10] + [int(c) for c in twid[1:]]
    total = sum(d * w for d, w in zip(digits, TWID_WEIGHTS))
    return total % 10 == 0


def luhn_valid(digits: str) -> bool:
    total = 0
    parity = len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def find_pii(text: str):
    findings = []

    emails = sorted(set(EMAIL_RE.findall(text)))
    if emails:
        findings.append(("Email 電子郵件", emails))

    twids = sorted({m for m in TWID_RE.findall(text) if twid_valid(m)})
    if twids:
        findings.append(("身分證字號", twids))

    ccs = []
    for m in CC_RE.findall(text):
        digits = re.sub(r"[ -]", "", m)
        if 13 <= len(digits) <= 19 and luhn_valid(digits):
            ccs.append(m.strip())
    ccs = sorted(set(ccs))
    if ccs:
        findings.append(("信用卡卡號", ccs))

    phones = sorted(set(PHONE_RE.findall(text)))
    if phones:
        findings.append(("電話號碼", phones))

    return findings


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        data = {}

    prompt = data.get("prompt") or ""
    findings = find_pii(prompt)

    if not findings:
        sys.exit(0)

    lines = ["偵測到疑似個人資訊 (PII)，此 prompt 已被拒絕，請移除或遮蔽後重新送出：", ""]
    for label, items in findings:
        preview = ", ".join(items[:5])
        more = "" if len(items) <= 5 else f" 等共 {len(items)} 筆"
        lines.append(f"- {label}：{preview}{more}")

    reason = "\n".join(lines)
    print(json.dumps({
        "decision": "block",
        "reason": reason,
        "systemMessage": reason,
        "continue": True,
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
