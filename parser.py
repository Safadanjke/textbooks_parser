from dataclasses import dataclass
import re
import os
import unicodedata
from typing import List, Dict

import pandas as pd
from pdf2image import convert_from_path
import pytesseract
import cv2
import numpy as np
from PIL import Image

from config import (
    MD_PATH, XLSX_PATH, PDF_PATH, TESSERACT_PATH,
    POPPLER_PATH, PATTERNS, ImageConfig, CleanConfig,
    ParserConfig, LatexConfig,
)


pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


@dataclass
class Question:
    """Модель вопроса учебника."""

    part: str
    number: str
    body: str
    image: str = ''


class TextbookParser:
    """Основной класс парсера."""

    def __init__(self):
        self.all_images = []
        self.global_img_index = 0

    @staticmethod
    def _normalize_question_number(raw_number: str) -> str:
        """Нормализует номер вопроса (заменяет латиницу на кириллицу)."""

        return raw_number.upper().replace('C', 'С')

    @staticmethod
    def _is_tail_fragment(chunk: str) -> bool:
        """Проверяет, является ли чанк хвостом предыдущего вопроса."""

        return (
            bool(re.match(r'^[ВCС]\d+\s+[А-Яа-я]', chunk))
            and len(chunk) < ParserConfig.TAIL_MAX_LEN
            and not chunk.endswith(('?', '.', '!'))
        )

    @staticmethod
    def _latex_unit_inside(unit: str) -> str:
        """Единица измерения внутри (\\mathrm)."""

        return LatexConfig.UNIT_LATEX_MAP.get(unit, f' {unit}')

    @staticmethod
    def _latexify_plain_segment(segment: str) -> str:
        """Преобразует равенства в тексте в формат LaTeX."""

        s = segment
        for rule in LatexConfig.LATEX_RULES:
            s = re.sub(
                rule['pattern'],
                rule['repl'],
                s,
                flags=rule.get('flags', 0)
            )
        return s

    @staticmethod
    def _latexify_markdown_body(text: str) -> str:
        """Оборачивает формулы в вид LaTeX."""

        if not LatexConfig.ENABLED:
            return text
        out: List[str] = []
        i = 0
        n = len(text)
        while i < n:
            if text[i] == '$':
                j = text.find('$', i + 1)
                if j == -1:
                    out.append(text[i:])
                    break
                out.append(text[i: j + 1])
                i = j + 1
            else:
                j = text.find('$', i)
                if j == -1:
                    out.append(
                        TextbookParser._latexify_plain_segment(text[i:]))
                    break
                out.append(TextbookParser._latexify_plain_segment(text[i:j]))
                i = j
        return ''.join(out)

    @staticmethod
    def _normalize_question_body(body: str) -> str:
        """Очищает текст вопроса от служебных маркеров."""

        body = re.sub(
            r'---\s*Страница\s*\d+\s*---', ' ', body, flags=re.IGNORECASE
        )
        body = re.sub(r'\bЧАСТЬ\s*\d+\b', ' ', body, flags=re.IGNORECASE)
        body = re.sub(r'\s*\n\s*', ' ', body)
        body = re.sub(r'\s{2,}', ' ', body)
        return body.strip()

    @staticmethod
    def _extract_body(subchunk: str, marker: str) -> str:
        """Извлекает текст вопроса из чанка с маркером."""

        body = subchunk[len(marker):].strip()
        body = re.sub(r'^\s*\|\s*', '', body)
        return re.sub(r'^\s*([ВCС]\d+)\s*\|?\s*', '', body)

    @staticmethod
    def _question_from_values(
        part: str,
        num: str,
        body: str,
        image: str = ''
    ) -> "Question":
        """Создаёт объект Question."""

        normalized = TextbookParser._normalize_question_body(body)
        latex_form = TextbookParser._latexify_markdown_body(normalized)

        return Question(
            part=part,
            number=num,
            body=latex_form,
            image=image,
        )

    @staticmethod
    def _should_start_new_question(
            stripped: str,
            line_index: int,
            lines: List[str],
            prev_line: str
    ) -> bool:
        """
        Определяет, начинается ли новый вопрос с текущей строки.

        Args:
            stripped: Обработанная строка
            line_index: Индекс строки в тексте
            lines: Все строки текста
            prev_line: Предыдущая строка

        """

        if not stripped or len(stripped) <= CleanConfig.MIN_QUESTION_LENGTH:
            return False
        if not (stripped[0].isupper() or stripped[0] in '+*•'):
            return False
        if not (
            re.search(r'\d', stripped)
            or (
                line_index > 0
                and not lines[line_index - 1].strip()
                and len(stripped) > 40
            )
        ):
            return False
        if prev_line.rstrip().endswith('-'):
            return False
        if re.match(r'^[\[\|]?\s*[ВВСCС]\d', stripped, re.IGNORECASE):
            return False
        if stripped.startswith('---') or stripped.startswith('ЧАСТЬ'):
            return False
        if stripped.lower().startswith('рис.') or stripped.startswith('http'):
            return False
        return True

    def _normalize_question_markers(self, text: str) -> str:
        """Нормализует маркеры вопросов в тексте."""

        text = re.sub(r'\[\s*с\s*з\s*\|', '[С3 |', text, flags=re.IGNORECASE)
        text = re.sub(r'\[\s*с\s*ч\s*\|', '[С4 |', text, flags=re.IGNORECASE)
        text = PATTERNS['question_marker'].sub(
            lambda m: (
                f"{ParserConfig.MARKER_QUESTION} "
                f"{m.group(1).upper()}{m.group(2)} |"
            ),
            text,
        )
        return re.sub(
            r'\n([ВCС])(\d+)\s+([А-Я][а-я]+)',
            lambda m: (
                f"\n{ParserConfig.MARKER_QUESTION} "
                f"{m.group(1).upper()}{m.group(2)} |{m.group(3)}"
            ),
            text,
            flags=re.IGNORECASE
        )

    def _split_by_page(self, chunks: List[str]) -> List[int]:
        """Определяет номер страницы для каждого чанка."""

        pages = []
        for index, chunk in enumerate(chunks):
            if index == 0:
                pages.append(1)
                continue
            page_match = PATTERNS['page_marker'].search(chunk)
            if page_match:
                pages.append(int(page_match.group(1)))
            else:
                pages.append(pages[-1] if pages else 1)
        return pages

    def _get_image_if_referenced(self, body: str, page_num: int) -> str:
        """Извлекает изображение, если оно упоминается в вопросе."""

        if PATTERNS['image_ref'].search(body):
            return self.get_image_for_question(body, page_num)
        return ''

    def _try_merge_short_image_tail(
            self,
            questions: List["Question"],
            body: str,
            part: str,
            page_num: int
    ) -> bool:
        """
        Пытается объединяет текст с изображением

        Args:
            questions: Список вопросов
            body: Текст хвоста
            part: Часть учебника
            page_num: Номер страницы

        """

        if (
            'Рис.' not in body
            or len(body) >= ParserConfig.SHORT_IMAGE_TAIL_MAX_LEN
        ):
            return False
        if not questions or questions[-1].part != part:
            return False
        questions[-1].body += ' ' + body
        if not questions[-1].image and PATTERNS['image_ref'].search(body):
            questions[-1].image = self.get_image_for_question(body, page_num)
        return True

    def _handle_marked_subchunk(
            self,
            subchunk: str,
            part: str,
            current_page: int,
            last_seen: Dict
    ) -> Dict:
        """Обрабатывает чанк с маркером вопроса."""

        match = re.match(r'([ВVCСс]\d+)?', subchunk, re.IGNORECASE)
        if match and match.group(1):
            num = self._normalize_question_number(match.group(1))
            letter = num[0]
            if num[1:].isdigit():
                number = int(num[1:])
                if number <= last_seen.get(letter, 0):
                    return {'merge': subchunk}
                last_seen[letter] = number
            body = self._extract_body(subchunk, match.group(1))
        else:
            num = 'AUTO'
            body = re.sub(r'^AUTO\s*', '', subchunk, flags=re.IGNORECASE)

        if not body:
            return {}

        return {
            'append': self._question_from_values(
                part=part,
                num=num,
                body=body,
                image=self._get_image_if_referenced(body, current_page),
            )
        }

    @staticmethod
    def _part_for_offset(chapter_parts: List, text_pos: int) -> str:
        """Определяет часть учебника по позиции в тексте."""

        selected = ParserConfig.DEFAULT_PART
        for pos, num in chapter_parts:
            if text_pos < pos:
                break
            selected = num
        return selected

    def _process_complex_chunk(
            self, chunk: str, part: str, current_page: int,
            questions: List["Question"], last_seen: Dict) -> None:
        """Обрабатывает сложный чанк с несколькими вопросами."""

        separator = (
            ParserConfig.MARKER_Q8
            if ParserConfig.MARKER_Q8 in chunk
            else ParserConfig.MARKER_NEW_QUESTION
        )
        parts = chunk.split(separator)

        if parts[0].strip():
            first_part = parts[0].strip()
            match = re.match(r'([ВVCСс]\d+)?', first_part, re.IGNORECASE)
            if match and match.group(1):
                num = self._normalize_question_number(match.group(1))
                last_seen[num[0]] = int(num[1:])
                body = re.sub(
                    r'^\s*\|\s*',
                    '',
                    first_part[len(match.group(1)):].strip()
                )
                questions.append(
                    self._question_from_values(
                        part=part,
                        num=num,
                        body=body,
                        image=self._get_image_if_referenced(body, current_page)
                    )
                )

        if len(parts) <= 1 or not parts[1].strip():
            return

        body = parts[1].strip()
        if self._try_merge_short_image_tail(
            questions, body, part, current_page
        ):
            return

        if separator == ParserConfig.MARKER_Q8:
            num = f'В{last_seen.get("В", 0) + 1}'
            last_seen['В'] += 1
        else:
            letter = 'В' if part == '2' else 'С'
            num = f"{letter}{last_seen.get(letter, 0) + 1}"
            last_seen[letter] += 1

        questions.append(
            self._question_from_values(
                part=part,
                num=num,
                body=body,
                image=self._get_image_if_referenced(body, current_page),
            )
        )

    def extract_images_from_page(
            self, pil_image: Image.Image, page_num: int) -> List[str]:
        """Вырезает изображения со страницы PDF."""

        img = np.array(pil_image)
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        os.makedirs("images", exist_ok=True)

        image_paths = []
        hashes = set()
        idx = 0

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h

            if area < ImageConfig.MIN_AREA:
                continue
            if w < ImageConfig.MIN_WIDTH or h < ImageConfig.MIN_HEIGHT:
                continue

            crop = img[y:y+h, x:x+w]
            small = cv2.resize(crop, ImageConfig.HASH_SIZE)
            hsh = hash(small.tobytes())

            if hsh in hashes:
                continue
            hashes.add(hsh)

            path = f"images/page_{page_num}_img_{idx}.png"
            cv2.imwrite(path, crop)
            image_paths.append((y, path))
            idx += 1

        image_paths.sort(key=lambda x: x[0])
        return [p for _, p in image_paths]

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Извлекает текст и изображения из PDF."""

        text = ""
        self.all_images = []
        self.global_img_index = 0

        images = convert_from_path(
            pdf_path, dpi=ImageConfig.DPI, poppler_path=POPPLER_PATH)

        for i, image in enumerate(images):
            page_num = i + 1
            page_text = pytesseract.image_to_string(image, lang='rus+eng')
            imgs = self.extract_images_from_page(image, page_num)
            self.all_images.extend(imgs)

            if page_text:
                text += f"\n\n--- Страница {page_num} ---\n\n"
                text += page_text + "\n"

        return text

    def fix_ocr(self, text: str) -> str:
        """
        Очищает текст от артефактов OCR

        Этапы очистки:
        1. Нормализация Unicode (NFKC)
        2. Замена специальных пробелов
        3. Замена латиницы на кириллицу
        4. Удаление дублей номеров
        5. Прямые замены частых ошибок
        6. Соединение разорванных строк
        7. Нормализация пробелов
        """
        text = unicodedata.normalize('NFKC', text)
        text = text.replace('\xa0', ' ')
        text = text.replace('\u200b', '')
        text = text.replace('\ufeff', '')
        text = text.replace('–', '-').replace('—', '-')

        text = text.translate(str.maketrans({
            **CleanConfig.LATIN_TO_CYRILLIC
        }))

        def normalize_match(m):
            g1 = m.group(1).upper().replace('С', 'C').replace('В', 'B')
            g2 = m.group(2).upper().replace('С', 'C').replace('В', 'B')
            if g1 == g2:
                return m.group(1) + ' '
            return m.group(0)

        text = re.sub(
            r'(?:^|\s)([ВCС]\d+)\s+([ВCС]\d+)\s+',
            normalize_match,
            text,
            flags=re.MULTILINE
        )

        for src, dst in CleanConfig.DIRECT_REPLACEMENTS.items():
            text = text.replace(src, dst)

        for pattern, replacement in CleanConfig.OCR_REGEX_RULES:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        text = re.sub(r'\n\+\n', '\n##Q8##\n', text)

        text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
        text = re.sub(r'\n(?==|\d)', '', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)

        return text

    def parse_questions(self, text: str) -> List['Question']:
        """Парсит вопросы из текста PDF."""

        lines = text.split('\n')
        processed_lines = []
        prev_line = ''

        for i, line in enumerate(lines):
            stripped = line.strip()
            is_question_start = self._should_start_new_question(
                stripped=stripped,
                line_index=i,
                lines=lines,
                prev_line=prev_line
            )
            if is_question_start:
                processed_lines.append('##NEWQ##')

            processed_lines.append(line)
            prev_line = stripped if stripped else prev_line

        text = '\n'.join(processed_lines)
        text = self._normalize_question_markers(text)

        chapter_parts = [
            (m.start(), m.group(1)) for m in PATTERNS['part'].finditer(text)
        ]

        chunks = text.split(ParserConfig.MARKER_QUESTION)
        questions = []
        last_seen = {'В': 0, 'С': 0}
        chunk_pages = self._split_by_page(chunks)

        current_page = 1
        marker_len = len(ParserConfig.MARKER_QUESTION)
        current_offset = len(chunks[0]) + marker_len
        for i, chunk in enumerate(chunks[1:], start=1):
            raw_chunk = chunk
            chunk = raw_chunk.strip()
            current_page = chunk_pages[i]
            current_part = self._part_for_offset(chapter_parts, current_offset)

            if (
                ParserConfig.MARKER_NEW_QUESTION in chunk
                or ParserConfig.MARKER_Q8 in chunk
            ):
                self._process_complex_chunk(
                    chunk=chunk,
                    part=current_part,
                    current_page=current_page,
                    questions=questions,
                    last_seen=last_seen,
                )
                current_offset += len(raw_chunk) + marker_len
                continue

            subchunks = chunk.split(ParserConfig.MARKER_NEW_QUESTION)

            for subchunk in subchunks:
                subchunk = subchunk.strip()
                if not subchunk:
                    continue
                if self._is_tail_fragment(subchunk):
                    if questions:
                        questions[-1].body += ' ' + subchunk
                    continue

                result = self._handle_marked_subchunk(
                    subchunk=subchunk,
                    part=current_part,
                    current_page=current_page,
                    last_seen=last_seen,
                )
                if result.get('merge'):
                    if questions:
                        questions[-1].body += ' ' + result['merge']
                    continue
                if result.get('append'):
                    questions.append(result['append'])

            current_offset += len(raw_chunk) + marker_len

        return questions

    def get_image_for_question(self, body: str, page_num: int) -> str:
        """Берёт следующую картинку из списка и возвращает путь к ней."""

        if self.global_img_index >= len(self.all_images):
            return ''

        path = self.all_images[self.global_img_index]
        self.global_img_index += 1
        return path

    def save_to_markdown(self, questions: List["Question"], output_path: str):
        """Сохраняет вопросы в Markdown формат."""

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            current_part = None
            for question in questions:
                if question.part != current_part:
                    current_part = question.part
                    if current_part == '2':
                        f.write(f"\\title{{\nЧАСТЬ {current_part}\n}}\n")
                    else:
                        f.write(f"\\section*{{ЧАСТЬ {current_part}}}\n\n")
                f.write(f"{question.number} {question.body}\n")
                if question.image:
                    f.write(f"\n{question.image}\n")
                f.write("\n")

    def save_to_excel(self, questions: List["Question"], output_path: str):
        """Сохраняет вопросы в Excel."""

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        df = pd.DataFrame([{
            'Часть': question.part,
            'Номер вопроса': question.number,
            'Вопрос': question.body,
            'Рисунок': question.image
        } for question in questions])

        df.to_excel(output_path, index=False, sheet_name='Sheet1')
        print(f"   Сохранено вопросов в Excel: {len(df)}")

    def run(self, pdf_path: str = PDF_PATH,
            md_path: str = MD_PATH,
            xlsx_path: str = XLSX_PATH):
        """Запускает пайплайн парсера."""

        print("Этап 1: Извлечение текста из PDF...")
        text = self.extract_text_from_pdf(pdf_path)
        print(f"   Извлечено символов: {len(text)}")

        print("Этап 2: Очистка текста...")
        text = self.fix_ocr(text)

        print("Этап 3: Парсинг вопросов...")
        questions = self.parse_questions(text)
        print(f"   Найдено вопросов: {len(questions)}")

        print("Этап 4: Сохранение в Markdown...")
        self.save_to_markdown(questions, md_path)

        print("Этап 5: Сохранение в Excel...")
        self.save_to_excel(questions, xlsx_path)

        print("Пайплайн завершен успешно!")
        print(f"   Markdown: {md_path}")
        print(f"   Excel: {xlsx_path}")


if __name__ == "__main__":
    parser = TextbookParser()
    parser.run()
