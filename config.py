"""
Конфигурация парсера учебников
"""
import os
import re

from dotenv import load_dotenv

load_dotenv()

# Пути к внешним зависимостям (Windows)
TESSERACT_PATH = os.getenv(
    'TESSERACT_PATH',
    r'C:\Program Files\Tesseract-OCR\tesseract.exe'
)
POPPLER_PATH = os.getenv(
    'POPPLER_PATH',
    r'C:\Program Files\poppler-25.12.0\Library\bin'
)
MD_PATH = 'output/промежуточный.md'
XLSX_PATH = 'output/результат.xlsx'
PDF_PATH = 'input/Учебник.pdf'

# Паттерны для парсинга
PATTERNS = {
    'image_ref': re.compile(r'рис\.?\s*(\d+)', re.IGNORECASE),
    'part': re.compile(r'ЧАСТЬ\s*(\d+)', re.IGNORECASE),
    'question_marker': re.compile(r'\[\s*([ВCС])\s*(\d+)\s*\|', re.IGNORECASE),
    # И латинские, и кириллические буквы
    'question_number': re.compile(r'([ВBСC])(\d+)', re.IGNORECASE),
    'page_marker': re.compile(r'--- Страница (\d+)'),
}


# Конфигурация извлечения изображений
class ImageConfig:
    MIN_AREA = 50_000
    MIN_WIDTH = 200
    MIN_HEIGHT = 200
    DPI = 300
    HASH_SIZE = (32, 32)


# Конфигурация OCR чистки
class CleanConfig:
    MIN_QUESTION_LENGTH = 20
    LATIN_TO_CYRILLIC = {
        'A': 'А', 'B': 'В', 'C': 'С', 'E': 'Е', 'H': 'Н',
        'K': 'К', 'M': 'М', 'O': 'О', 'P': 'Р', 'T': 'Т', 'X': 'Х',
        'a': 'а', 'c': 'с', 'e': 'е', 'o': 'о', 'p': 'р', 'y': 'у', 'x': 'х'
    }

    DIRECT_REPLACEMENTS = {
        'ММН': 'мин',
        'АUТО': 'AUTO',
        'соверптает': 'совершает',
        '3а ': 'За ',
        'со скоростью и =': 'со скоростью v =',
    }

    OCR_REGEX_RULES = [
        # OCR scientific notation
        (r'(\d+[,.]\d+)\s*-\s*10(\d)\b', r'\1 * 10^\2'),
        # Repeated "=="
        (r'==+', r'='),
        # "|" around question number
        (r'\|\s*([ВCС]\d+)\s*\|', r'\1 '),
        # Typical var misreads
        (r'\bАt\b', r'Δt'),
        (r'\bt,\s*=', r't1 ='),
        (r'\bd,\s*=', r'd1 ='),
        (r'\bа,\s+', r'а1 '),
        (r'\bи,\s*=', r'v0 ='),
        (r'\bТ\s*=\s*=\s*', r'T = '),
        (r'\bВ\s*=\s*=\s*', r'R = '),
        (r'(расстояни\w*\s+)\[(\s*=)', r'\1l\2'),
        (r'(путь\s+)8(\s*=)', r'\1s\2'),
        (r'(скорост(?:ью|и)\s+)и(\s*=)', r'\1v\2'),
        (r'(скорост(?:ью|и)\s+)о(\s*=)', r'\1v\2'),
        (r'(со\s+скоростью\s+)и(\s*=)', r'\1v\2'),
        (r'(со\s+скоростью\s+)о(\s*=)', r'\1v\2'),
        (r'(со\s+скоростью\s+)[иuоo](\s*=)', r'\1v\2'),
        (r'(со\s+скоростью\s+)[иuоo](\s*=\s*\d+[,.]?\d*\s*км/ч)', r'\1v\2'),
        (r'(со\s+скоростью\s+)\S(\s*=\s*\d+[,.]?\d*\s*км/ч)', r'\1v\2'),
        (r'(радиус\w*\s+)В(\s*=)', r'\1R\2'),
        (r'(минутной стрелки[^.\n]{0,40})\bВ(\s*=)', r'\1R\2'),
        (r'(угол[^.\n]{0,220})\bо(\s*=\s*\d+\s*°)', r'\1α\2'),
        (r'(составляет\s+)[оo](\s*=\s*\d+\s*°)', r'\1α\2'),
        (r'(диаметр\s+)4\.(\s*=)', r'\1d3\2'),
        (r'(диаметром)\s*4\.(\s*=)', r'\1 d2\2'),
        # Missing spacing between vars
        (r'(\d+\s*м)\s*и\s*А\s*=', r'\1 и A='),
        (r'([A-Za-zА-Яа-я])=([0-9])', r'\1 = \2'),
        (r'([A-Za-zА-Яа-я])\s*=\s*([0-9])', r'\1 = \2'),
    ]


class ParserConfig:
    MARKER_QUESTION = '##Q##'
    MARKER_NEW_QUESTION = '##NEWQ##'
    MARKER_Q8 = '##Q8##'
    DEFAULT_PART = '1'
    PART_BY_FIRST_PAGE = '2'
    PART_BY_OTHER_PAGES = '3'
    TAIL_MAX_LEN = 120
    SHORT_IMAGE_TAIL_MAX_LEN = 100
