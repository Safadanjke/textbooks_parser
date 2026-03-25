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


class LatexConfig:
    """
    Правила оборачивания фрагментов
    «переменная = значение» в $...$ для Markdown.

    """

    ENABLED = True

    UNIT_SUFFIXES = (
        'км/ч',
        'об/мин',
        'рад/с',
        'м/с?',
        'м/с',
        'мм',
        'см',
        'км',
        'сут',
        'мин',
        'м',
        'с',
        '°',
    )

    # Таблица замены единиц для _latex_unit_inside
    UNIT_LATEX_MAP = {
        'км/ч': r' \mathrm{~km/h}',
        'об/мин': r' \mathrm{~min}^{-1}',
        'рад/с': r' \mathrm{~rad/s}',
        'м/с?': r' \mathrm{~m/s}^{2}',
        'м/с': r' \mathrm{~m/s}',
        'мм': r' \mathrm{~mm}',
        'см': r' \mathrm{~cm}',
        'км': r' \mathrm{~km}',
        'сут': r' \mathrm{~d}',
        'мин': r' \mathrm{~min}',
        'м': r' \mathrm{~m}',
        'с': r' \mathrm{~s}',
        '°': r'^{\circ}',
    }

    # Правила LaTeX-преобразования
    LATEX_RULES = [
        {'pattern': r'(\d)м/с', 'repl': lambda m: f'{m.group(1)} м/с'},
        {'pattern': r'(\d)м(?=\s|и|\.|,|\?|\)|$|/|\s+и\s)', 'repl': lambda m: f'{m.group(1)} м'},
        {
            'pattern': r'(?<![A-Za-zА-Яа-я0-9_$])(R|r)\s*=\s*([0-9]+[,.][0-9]+)\s*\*\s*10\^(\d+)\s*км\b',
            'repl': lambda m: f'$R={m.group(2)} \\cdot 10^{{{m.group(3)}}} \\mathrm{{~km}}$',
        },
        {
            'pattern': r'(?<![A-Za-zА-Яа-я0-9_$])Δt\s*=\s*([0-9]+[,.]?[0-9]*)',
            'repl': lambda m: f'$\\Delta t={m.group(1)}$',
        },
        {
            'pattern': r'(?<![A-Za-zА-Яа-я0-9_$])\bd([123])\s*=\s*(\d+)\s*(мм|м)(?=\s|[,.;?!)]|\)|$)',
            'repl': lambda m: f'$d_{{{m.group(1)}}}={m.group(2)}{LatexConfig.UNIT_LATEX_MAP.get(m.group(3), f" {m.group(3)}")}$',
            'flags': re.IGNORECASE,
        },
        {
            'pattern': r'(?<![A-Za-zА-Яа-я0-9_$])\bt1\s*=\s*([0-9]+[,.]?[0-9]*)\s*с\b',
            'repl': lambda m: f'$t_{{1}}={m.group(1)}{LatexConfig.UNIT_LATEX_MAP.get("с", " с")}$',
            'flags': re.IGNORECASE,
        },
        {
            'pattern': r'(?<![A-Za-zА-Яа-я0-9_$])\bv0\s*=\s*([0-9]+[,.]?[0-9]*)\s*(м/с\?|м/с|км/ч)?',
            'repl': lambda m: f'$v_{{0}}={m.group(1)}{LatexConfig.UNIT_LATEX_MAP.get(m.group(2), "") if m.group(2) else ""}$',
            'flags': re.IGNORECASE,
        },
        {
            'pattern': r'(?<![A-Za-zА-Яа-я0-9_$])\b(?:a1|а1)\s*=\s*([0-9]+[,.]?[0-9]*)\s*(м/с\?|м/с)?',
            'repl': lambda m: f'$a_{{1}}={m.group(1)}{LatexConfig.UNIT_LATEX_MAP.get(m.group(2) or "м/с?", "")}$',
            'flags': re.IGNORECASE,
        },
        {
            'pattern': r'(?<![A-Za-zА-Яа-я0-9_$])\b(?:φ|ф)\s*=\s*([0-9]+[,.]?[0-9]*)\s*°',
            'repl': lambda m: f'$\\varphi={m.group(1)}{LatexConfig.UNIT_LATEX_MAP.get("°", "")}$',
            'flags': re.IGNORECASE,
        },
        {
            'pattern': r'(?<![A-Za-zА-Яа-я0-9_$])\bα\s*=\s*([0-9]+[,.]?[0-9]*)\s*°',
            'repl': lambda m: f'$\\alpha={m.group(1)}{LatexConfig.UNIT_LATEX_MAP.get("°", "")}$',
        },
        {
            'pattern': r'(?<![A-Za-zА-Яа-я0-9_$])\bп\s*=\s*(\d+)\s*об/мин',
            'repl': r'$n=\1$ об/мин',
            'flags': re.IGNORECASE,
        },
        {
            'pattern': r'(?<![A-Za-zА-Яа-я0-9_$])\bа\s*=\s*([0-9]+[,.][0-9]+)\s*м/с\?',
            'repl': lambda m: f'$a={m.group(1)} \\mathrm{{~m/s}}^{{2}}$',
            'flags': re.IGNORECASE,
        },
        {
            'pattern': r'(?<![A-Za-zА-Яа-я0-9_$])\bа\s*=\s*([0-9]+[,.][0-9]+)\s*м/с\b',
            'repl': lambda m: f'$a={m.group(1)} \\mathrm{{~m/s}}^{{2}}$',
            'flags': re.IGNORECASE,
        },
        {
            'pattern': r'(?<![A-Za-zА-Яа-я0-9_$])\bv\s*=\s*([0-9]+)\s*м/с',
            'repl': lambda m: f'$v={m.group(1)} \\mathrm{{~m/s}}$',
            'flags': re.IGNORECASE,
        },
        {
            'pattern': r'(?<![A-Za-zА-Яа-я0-9_$])\br\s*=\s*([0-9]+)\s*м\b',
            'repl': lambda m: f'$r={m.group(1)} \\mathrm{{~m}}$',
            'flags': re.IGNORECASE,
        },
        {
            'pattern': r'(?<![A-Za-zА-Яа-я0-9_$])\bA\s*=\s*([0-9]+)\s*м\b',
            'repl': lambda m: f'$R={m.group(1)} \\mathrm{{~m}}$',
        },
        {
            'pattern': r'(?<![A-Za-zА-Яа-я0-9_$])[ТT]\s*=\s*([0-9]+(?:[,.][0-9]+)?)\s*сут\b',
            'repl': lambda m: f'$T={m.group(1)}$ сут',
        },
        {
            'pattern': r'(?<![A-Za-zА-Яа-я0-9_$])[ТT]\s*=\s*([0-9]+(?:[,.][0-9]+)?)\s*ч\b',
            'repl': lambda m: f'$T={m.group(1)}$ ч',
        },
        {
            'pattern': r'(?<![A-Za-zА-Яа-я0-9_$])[ТT]\s*=\s*(\d+)\s*,\s*при\b',
            'repl': lambda m: f'$T={m.group(1)}$, при',
        },
        {
            'pattern': (
                r'(?<![A-Za-zА-Яа-я0-9_$])([RTvlsnLV])\s*=\s*([0-9]+(?:[,.][0-9]+)?)'
                r'(?:\s+(' + '|'.join(re.escape(u) for u in UNIT_SUFFIXES) + r'))?'
                r'(?!\s*\*)'
                r'(?=\s|[,.;?!)]|\)|$|[А-Яа-яЁё])'
            ),
            'repl': lambda m: (
                f'${m.group(1)}={m.group(2)}'
                f'{LatexConfig.UNIT_LATEX_MAP.get(m.group(3), "") if m.group(3) else ""}$'
            ),
        },
        {
            'pattern': r'(?<![A-Za-zА-Яа-я0-9_$])\bs\s*=\s*([0-9]+)\s*м\b',
            'repl': lambda m: f'$s={m.group(1)} \\mathrm{{~m}}$',
            'flags': re.IGNORECASE,
        },
        {
            'pattern': r'(?<![A-Za-zА-Яа-я0-9_$])\bl\s*=\s*([0-9]+(?:[,.][0-9]+)?)\s*м\b',
            'repl': lambda m: f'$l={m.group(1)} \\mathrm{{~m}}$',
            'flags': re.IGNORECASE,
        },
        {
            'pattern': r'(?<![A-Za-zА-Яа-я0-9_$])\bL\s*=\s*([0-9]+)\s*см\b',
            'repl': lambda m: f'$L={m.group(1)} \\mathrm{{~cm}}$',
            'flags': re.IGNORECASE,
        },
    ]
