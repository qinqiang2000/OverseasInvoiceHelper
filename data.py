import pandas as pd
import os
from openpyxl import Workbook


class ExcelHandler:
    def __init__(self, file_path):
        self.file_path = file_path
        self.df = self.load_excel_to_dataframe()

    def load_excel_to_dataframe(self):
        if not os.path.exists(self.file_path):
            # 创建一个新的 DataFrame 并设置列名
            df = pd.DataFrame(columns=['filename', 'page', 'result', 'down'])
            # 保存这个新的空白 DataFrame 到 Excel 文件
            df.to_excel(self.file_path, index=False, engine='openpyxl')
            return df
        else:
            return pd.read_excel(self.file_path, engine='openpyxl')

    def add_row_to_dataframe(self, new_data):
        new_row = pd.DataFrame([new_data])
        self.df = self.df.append(new_row, ignore_index=True)

    def save_dataframe_to_excel(self):
        self.df.to_excel(self.file_path, index=False, engine='openpyxl')

    def add_key_to_down(self, filename, page, ret, key):
        match = self.df[(self.df['filename'] == filename) & (self.df['page'] == page)]

        if not match.empty:
            row_index = match.index[0]
            current_down = match.at[row_index, 'down']
            if key not in current_down:
                current_down.append(key)
            self.df.at[row_index, 'down'] = current_down
        else:
            new_row = {'filename': filename, 'page': page, 'result': ret, 'down': [key]}
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
