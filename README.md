# Parser textbooks 📚

Парсер PDF-учебников с распознаванием текста и извлечением изображений.

## Что делает

1. **Извлекает текст** из сканированных PDF через OCR (Tesseract)
2. **Вырезает изображения** (рисунки, схемы) из страниц
3. **Очищает текст** от артефактов OCR
4. **Распознаёт вопросы** с нумерацией (В1, В2, С1, С2 и т.д.)
5. **Сохраняет результаты** в Markdown и Excel

## Требования

### Системные

1. **Python 3.9+**

2. **Tesseract OCR** (распознавание текста)
   - Windows: https://github.com/UB-Mannheim/tesseract/wiki
   - Установите в `C:\Program Files\Tesseract-OCR`
   - Выберите русский язык при установке

3. **Poppler** (конвертация PDF → изображения)
   - Windows: https://github.com/oschwartz10612/poppler-windows/releases
   - Распакуйте в `C:\Program Files\poppler`

### Python зависимости

```bash
pip install -r requirements.txt
```

Или вручную:
```bash
pip install pdfplumber openpyxl pandas regex pytesseract pdf2image Pillow opencv-python numpy
```

## Установка

1. Клонируйте или скачайте проект
2. Установите системные зависимости (Tesseract + Poppler)
3. Установите Python зависимости:

```bash
cd путь_к_файлу\Parser_notebooks
python -m venv venv
source venv\Scripts\activate
pip install -r requirements.txt
```

## Запуск

### Базовый запуск

```bash
python parser.py
```

Парсер обработает `input/Учебник.pdf` и создаст:
- `output/промежуточный.md` — текст с вопросами
- `output/результат.xlsx` — таблица с вопросами
- `images/` — извлечённые изображения

### Свои пути

Откройте `parser.py` и измените в методе `run()`:

```python
parser.run(
    pdf_path='input/мой_учебник.pdf',
    md_path='output/мой.md',
    xlsx_path='output/мой.xlsx'
)
```

## Структура проекта

```
parser_notebooks/
├── parser.py           # Главный модуль
├── config.py           # Конфигурация и паттерны
├── requirements.txt    # Python зависимости
├── input/              # Входные PDF файлы
├── output/             # Результаты парсинга
│   ├── промежуточный.md
│   └── результат.xlsx
└── images/             # Извлечённые изображения
```
