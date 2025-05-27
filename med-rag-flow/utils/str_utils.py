
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

def replace_t_with_space(list_of_documents):
    """
    将每个文档的页面内容中的所有制表符('\t')替换为空格

    参数:
        list_of_documents: 一个文档对象列表，每个对象都有一个'page_content'属性。

    返回:
        修改后的文档列表，其中的制表符已被替换为空格。
    """

    for doc in list_of_documents:
        doc.page_content = doc.page_content.replace('\t', ' ')  # 将制表符替换为空格
    return list_of_documents