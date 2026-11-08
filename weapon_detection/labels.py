from collections import Counter


def normalize_label(label):
    return str(label).strip()


def normalize_summary(summary):
    normalized = Counter()
    for label, count in summary.items():
        normalized[normalize_label(label)] += count
    return dict(normalized)


def normalize_text(text):
    return text
