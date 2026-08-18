import sys, openpyxl
sys.stdout.reconfigure(encoding='utf-8')
path = r'D:\Rate File Template\Rate_File_Template_Completion_Freightify\RE_ Tariff Examples\AAW Global National Import Sea LCL Tariff 1st July 2026 – 14th July 2026.xlsm'
wb = openpyxl.load_workbook(path, data_only=True)
print('Sheets:', wb.sheetnames)
for sn in wb.sheetnames:
    ws = wb[sn]
    if ws.max_row and ws.max_row > 1:
        print(f"\nSheet '{sn}': Rows={ws.max_row}, Cols={ws.max_column}")
        for r in range(1, min(ws.max_row + 1, 12)):
            print(f"  Row {r}:", [str(ws.cell(r, c).value or '')[:35] for c in range(1, min((ws.max_column or 1) + 1, 20))])
