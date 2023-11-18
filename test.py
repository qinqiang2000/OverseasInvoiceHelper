import pandas as pd


def csv_to_markdown(csv_file):
    # 读取CSV文件
    data = pd.read_csv(csv_file)

    # 将数据转换为Markdown格式的表格
    markdown_table = data.to_markdown()

    return markdown_table


# 调用函数并指定你的CSV文件路径
csv_file_path = '/Users/qinqiang02/Desktop/热点问题管理_20231116.csv'
markdown_table = csv_to_markdown(csv_file_path)

# 将Markdown表格保存到文件
output_file = '/Users/qinqiang02/Desktop/output.md'  # 指定输出文件的路径和名称
with open(output_file, 'w') as f:
    f.write(markdown_table)

print(f'Markdown表格已保存到文件：{output_file}')