import pandas as pd
import os


class ExcelHandler:
    def __init__(self, file_path):
        self.file_path = file_path
        self.df = self.load_excel_to_dataframe()

    def load_excel_to_dataframe(self):
        if not os.path.exists(self.file_path):
            # 创建一个新的 DataFrame 并设置列名
            df = pd.DataFrame(columns=['filename', 'page', 'result', 'anno', 'down', 'raw'])
            # 保存这个新的空白 DataFrame 到 Excel 文件
            df.to_excel(self.file_path, index=False, engine='openpyxl')
            return df
        else:
            return pd.read_excel(self.file_path, engine='openpyxl')

    def add_row_to_dataframe(self, new_data):
        # 先判断是否已经存在这一行
        match = self.df[(self.df['filename'] == new_data['filename']) & (self.df['page'] == new_data['page'])]
        if not match.empty:
            row_index = match.index[0]
            # 保留原有的标注数据
            new_data['anno'] = match.at[row_index, 'anno']
            # 删除原来的行
            self.df.drop(index=row_index, inplace=True)

        new_row = pd.DataFrame([new_data])
        self.df = self.df._append(new_row, ignore_index=True)

    def save_dataframe_to_excel(self):
        self.df.to_excel(self.file_path, index=False, engine='openpyxl')

    def match(self, filename, page):
        match = self.df[(self.df['filename'] == filename) & (self.df['page'] == page)]
        return match

    def update_row(self, filename, page, ret, anno, key, raw=""):
        match = self.df[(self.df['filename'] == filename) & (self.df['page'] == page)]

        if not match.empty:
            row_index = match.index[0]
            current_down = match.at[row_index, 'down']
            if key not in current_down:
                if current_down == '[]':
                    current_down = []
                current_down.append(key)
            self.df.at[row_index, 'down'] = current_down
            self.df.at[row_index, 'anno'] = anno
            if raw != "":
                self.df.at[row_index, 'raw'] = raw
        else:
            new_row = {'filename': filename, 'page': page, 'result': ret, 'anno': anno, 'down': [key], 'raw': raw}
            self.df = self.df._append(new_row, ignore_index=True)

    def remove_key_from_down(self, filename, page, key):
        match = self.df[(self.df['filename'] == filename) & (self.df['page'] == page)]

        if match.empty:
            return

        row_index = match.index[0]
        current_down = match.at[row_index, 'down']
        if key in current_down:
            current_down.remove(key)
        # 如果current_down为空，删除这一行
        if not current_down:
            self.df.drop(index=row_index, inplace=True)
        else:
            self.df.at[row_index, 'down'] = current_down
