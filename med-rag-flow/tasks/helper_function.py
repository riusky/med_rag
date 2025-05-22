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


def extract_text_from_markdown(md_path):
    """
    从Markdown文件中提取文本内容（保留原始格式，包括Markdown标记）
    
    参数:
    md_path (str): Markdown文件的路径
    
    返回:
    str: 文件中的原始文本内容（包含Markdown语法）
    """
    # 以UTF-8编码打开文件（避免中文乱码）
    with open(md_path, 'r', encoding='utf-8') as f:
        # 读取全部内容并返回
        return f.read()