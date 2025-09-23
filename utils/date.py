# utils/date.py
# Funções de manipulação de datas

from datetime import datetime

def fmt_date(date_str=None) -> str:
    """
    Formata data no padrão DD-MM-YYYY.
    Se nenhuma data for fornecida, usa a data atual.
    """
    if date_str:
        return datetime.strptime(date_str, "%d-%m-%Y").strftime("%d-%m-%Y")
    return datetime.now().strftime("%d-%m-%Y")
