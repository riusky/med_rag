
def optimize_str(title: str) -> str:
    """字符串优化处理"""
    replacements = [
        ('“ ', '“'), (' ”', '”'),
        (' （ ', '('), (' ） ', ')'),
        (' （', '('), (' ）', ')'),
        ('（ ', '('), ('） ', ')'),
        (' / ', '/'), ('：', ':'),
        ('【', '['), ('】', ']'),
        ('　', ' ')
    ]
    for old, new in replacements:
        title = title.replace(old, new)
    return title.strip()