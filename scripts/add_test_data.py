#!/usr/bin/env python
"""
Script to add test data to database.
Creates themes, questions, and bots for testing.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import db_session
from database.models import Theme, Question, User
from utils.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def create_themes(session):
    """Create test themes."""
    themes_data = [
        {'code': 'movies', 'name': 'Кино', 'description': 'Вопросы о кино и фильмах'},
        {'code': 'science', 'name': 'Наука', 'description': 'Вопросы о науке'},
        {'code': 'sport', 'name': 'Спорт', 'description': 'Вопросы о спорте'},
        {'code': 'geography', 'name': 'География', 'description': 'Вопросы о географии'},
        {'code': 'history', 'name': 'История', 'description': 'Вопросы об истории'},
    ]
    
    created = 0
    for theme_data in themes_data:
        existing = session.query(Theme).filter(Theme.code == theme_data['code']).first()
        if not existing:
            theme = Theme(**theme_data)
            session.add(theme)
            created += 1
            logger.info(f"Created theme: {theme_data['name']}")
        else:
            logger.info(f"Theme already exists: {theme_data['name']}")
    
    session.commit()
    return created


def create_questions(session):
    """Create test questions."""
    questions_data = [
        # Кино (20 вопросов)
        {
            'theme_code': 'movies',
            'question_text': 'Какой актер сыграл Тони Старка в киновселенной Marvel?',
            'option_a': 'Крис Эванс',
            'option_b': 'Роберт Дауни-младший',
            'option_c': 'Крис Хемсворт',
            'option_d': 'Марк Руффало',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'movies',
            'question_text': 'В каком году вышел фильм "Титаник"?',
            'option_a': '1995',
            'option_b': '1997',
            'option_c': '1999',
            'option_d': '2001',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'movies',
            'question_text': 'Кто режиссер фильма "Криминальное чтиво"?',
            'option_a': 'Мартин Скорсезе',
            'option_b': 'Квентин Тарантино',
            'option_c': 'Кристофер Нолан',
            'option_d': 'Стивен Спилберг',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'movies',
            'question_text': 'Какой фильм получил Оскар за лучший фильм в 2020 году?',
            'option_a': 'Джокер',
            'option_b': 'Паразиты',
            'option_c': '1917',
            'option_d': 'Однажды в Голливуде',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'movies',
            'question_text': 'Кто сыграл главную роль в фильме "Форрест Гамп"?',
            'option_a': 'Брэд Питт',
            'option_b': 'Леонардо ДиКаприо',
            'option_c': 'Том Хэнкс',
            'option_d': 'Мэтт Деймон',
            'correct_option': 'C',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'movies',
            'question_text': 'В каком году вышел первый фильм "Звездные войны"?',
            'option_a': '1975',
            'option_b': '1977',
            'option_c': '1979',
            'option_d': '1981',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'movies',
            'question_text': 'Какой фильм является самым кассовым в истории?',
            'option_a': 'Титаник',
            'option_b': 'Аватар',
            'option_c': 'Мстители: Финал',
            'option_d': 'Аватар: Путь воды',
            'correct_option': 'D',
            'difficulty': 'hard'
        },
        {
            'theme_code': 'movies',
            'question_text': 'Кто режиссер фильма "Начало" (Inception)?',
            'option_a': 'Кристофер Нолан',
            'option_b': 'Дени Вильнёв',
            'option_c': 'Ридли Скотт',
            'option_d': 'Дэвид Финчер',
            'correct_option': 'A',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'movies',
            'question_text': 'Какой актер сыграл Джокера в фильме 2019 года?',
            'option_a': 'Хит Леджер',
            'option_b': 'Хоакин Феникс',
            'option_c': 'Джек Николсон',
            'option_d': 'Джаред Лето',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'movies',
            'question_text': 'В каком фильме звучит фраза "Я буду возвращаться"?',
            'option_a': 'Хищник',
            'option_b': 'Терминатор',
            'option_c': 'Коммандо',
            'option_d': 'Бегущий человек',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'movies',
            'question_text': 'Кто сыграл Нео в фильме "Матрица"?',
            'option_a': 'Киану Ривз',
            'option_b': 'Хью Джекман',
            'option_c': 'Джейсон Стэйтем',
            'option_d': 'Вин Дизель',
            'correct_option': 'A',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'movies',
            'question_text': 'Какой фильм получил больше всего Оскаров?',
            'option_a': 'Титаник',
            'option_b': 'Властелин колец: Возвращение короля',
            'option_c': 'Бен-Гур',
            'option_d': 'Всё о Еве',
            'correct_option': 'C',
            'difficulty': 'hard'
        },
        {
            'theme_code': 'movies',
            'question_text': 'Кто режиссер фильма "Криминальное чтиво"?',
            'option_a': 'Мартин Скорсезе',
            'option_b': 'Квентин Тарантино',
            'option_c': 'Дэвид Линч',
            'option_d': 'Пол Томас Андерсон',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'movies',
            'question_text': 'В каком году вышел фильм "Крестный отец"?',
            'option_a': '1970',
            'option_b': '1972',
            'option_c': '1974',
            'option_d': '1976',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'movies',
            'question_text': 'Кто сыграл Гарри Поттера в фильмах?',
            'option_a': 'Руперт Гринт',
            'option_b': 'Дэниел Рэдклифф',
            'option_c': 'Том Фелтон',
            'option_d': 'Мэттью Льюис',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'movies',
            'question_text': 'Какой фильм является продолжением "Терминатора 2"?',
            'option_a': 'Терминатор 3',
            'option_b': 'Терминатор: Генезис',
            'option_c': 'Терминатор: Темная судьба',
            'option_d': 'Терминатор: Спасение',
            'correct_option': 'A',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'movies',
            'question_text': 'Кто режиссер фильма "Интерстеллар"?',
            'option_a': 'Кристофер Нолан',
            'option_b': 'Дени Вильнёв',
            'option_c': 'Ридли Скотт',
            'option_d': 'Стивен Спилберг',
            'correct_option': 'A',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'movies',
            'question_text': 'В каком фильме звучит музыка "Also sprach Zarathustra"?',
            'option_a': '2001: Космическая одиссея',
            'option_b': 'Звездные войны',
            'option_c': 'Космическая одиссея',
            'option_d': 'Интерстеллар',
            'correct_option': 'A',
            'difficulty': 'hard'
        },
        {
            'theme_code': 'movies',
            'question_text': 'Кто сыграл Железного человека в MCU?',
            'option_a': 'Крис Эванс',
            'option_b': 'Роберт Дауни-младший',
            'option_c': 'Крис Хемсворт',
            'option_d': 'Марк Руффало',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'movies',
            'question_text': 'Какой фильм получил Оскар за лучший фильм в 1994 году?',
            'option_a': 'Список Шиндлера',
            'option_b': 'Форрест Гамп',
            'option_c': 'Криминальное чтиво',
            'option_d': 'Побег из Шоушенка',
            'correct_option': 'B',
            'difficulty': 'hard'
        },
        # Наука (20 вопросов)
        {
            'theme_code': 'science',
            'question_text': 'Какая планета ближе всего к Солнцу?',
            'option_a': 'Венера',
            'option_b': 'Меркурий',
            'option_c': 'Земля',
            'option_d': 'Марс',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'science',
            'question_text': 'Сколько хромосом у человека?',
            'option_a': '42',
            'option_b': '44',
            'option_c': '46',
            'option_d': '48',
            'correct_option': 'C',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'science',
            'question_text': 'Какая скорость света в вакууме?',
            'option_a': '300 000 км/с',
            'option_b': '299 792 458 м/с',
            'option_c': '150 000 км/с',
            'option_d': '450 000 км/с',
            'correct_option': 'B',
            'difficulty': 'hard'
        },
        {
            'theme_code': 'science',
            'question_text': 'Какая самая большая планета Солнечной системы?',
            'option_a': 'Сатурн',
            'option_b': 'Юпитер',
            'option_c': 'Нептун',
            'option_d': 'Уран',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'science',
            'question_text': 'Сколько костей в теле взрослого человека?',
            'option_a': '196',
            'option_b': '206',
            'option_c': '216',
            'option_d': '226',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'science',
            'question_text': 'Какой химический элемент обозначается символом Au?',
            'option_a': 'Серебро',
            'option_b': 'Золото',
            'option_c': 'Алюминий',
            'option_d': 'Уран',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'science',
            'question_text': 'Какая температура кипения воды при нормальном давлении?',
            'option_a': '90°C',
            'option_b': '100°C',
            'option_c': '110°C',
            'option_d': '120°C',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'science',
            'question_text': 'Сколько спутников у Марса?',
            'option_a': '0',
            'option_b': '1',
            'option_c': '2',
            'option_d': '3',
            'correct_option': 'C',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'science',
            'question_text': 'Какой газ составляет большую часть атмосферы Земли?',
            'option_a': 'Кислород',
            'option_b': 'Азот',
            'option_c': 'Углекислый газ',
            'option_d': 'Аргон',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'science',
            'question_text': 'Какая самая маленькая частица вещества?',
            'option_a': 'Атом',
            'option_b': 'Молекула',
            'option_c': 'Электрон',
            'option_d': 'Кварк',
            'correct_option': 'A',
            'difficulty': 'hard'
        },
        {
            'theme_code': 'science',
            'question_text': 'Сколько планет в Солнечной системе?',
            'option_a': '7',
            'option_b': '8',
            'option_c': '9',
            'option_d': '10',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'science',
            'question_text': 'Какая формула воды?',
            'option_a': 'H2O',
            'option_b': 'CO2',
            'option_c': 'O2',
            'option_d': 'H2SO4',
            'correct_option': 'A',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'science',
            'question_text': 'Какой орган человека самый большой?',
            'option_a': 'Печень',
            'option_b': 'Легкие',
            'option_c': 'Кожа',
            'option_d': 'Кишечник',
            'correct_option': 'C',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'science',
            'question_text': 'Сколько минут нужно свету, чтобы дойти от Солнца до Земли?',
            'option_a': '6',
            'option_b': '8',
            'option_c': '10',
            'option_d': '12',
            'correct_option': 'B',
            'difficulty': 'hard'
        },
        {
            'theme_code': 'science',
            'question_text': 'Какая самая твердая природная субстанция на Земле?',
            'option_a': 'Золото',
            'option_b': 'Алмаз',
            'option_c': 'Платина',
            'option_d': 'Титан',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'science',
            'question_text': 'Сколько камер в сердце человека?',
            'option_a': '2',
            'option_b': '3',
            'option_c': '4',
            'option_d': '5',
            'correct_option': 'C',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'science',
            'question_text': 'Какой химический элемент имеет атомный номер 1?',
            'option_a': 'Гелий',
            'option_b': 'Водород',
            'option_c': 'Литий',
            'option_d': 'Углерод',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'science',
            'question_text': 'Какая самая высокая гора на Земле?',
            'option_a': 'К2',
            'option_b': 'Эверест',
            'option_c': 'Килиманджаро',
            'option_d': 'Мак-Кинли',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'science',
            'question_text': 'Сколько спутников у Юпитера?',
            'option_a': '50-60',
            'option_b': '70-80',
            'option_c': '90-100',
            'option_d': 'Более 90',
            'correct_option': 'D',
            'difficulty': 'hard'
        },
        {
            'theme_code': 'science',
            'question_text': 'Какая температура замерзания воды?',
            'option_a': '-10°C',
            'option_b': '0°C',
            'option_c': '10°C',
            'option_d': '32°C',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        # Спорт (20 вопросов)
        {
            'theme_code': 'sport',
            'question_text': 'В каком году проходила Олимпиада в Москве?',
            'option_a': '1976',
            'option_b': '1980',
            'option_c': '1984',
            'option_d': '1988',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'sport',
            'question_text': 'Сколько игроков в футбольной команде на поле?',
            'option_a': '10',
            'option_b': '11',
            'option_c': '12',
            'option_d': '9',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'sport',
            'question_text': 'В каком виде спорта используется ракетка?',
            'option_a': 'Футбол',
            'option_b': 'Теннис',
            'option_c': 'Баскетбол',
            'option_d': 'Волейбол',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'sport',
            'question_text': 'Сколько игроков в баскетбольной команде на площадке?',
            'option_a': '4',
            'option_b': '5',
            'option_c': '6',
            'option_d': '7',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'sport',
            'question_text': 'В каком году проходил чемпионат мира по футболу в России?',
            'option_a': '2016',
            'option_b': '2018',
            'option_c': '2020',
            'option_d': '2022',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'sport',
            'question_text': 'Сколько сетов в теннисном матче для победы у мужчин?',
            'option_a': '2 из 3',
            'option_b': '3 из 5',
            'option_c': '2 из 4',
            'option_d': '3 из 6',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'sport',
            'question_text': 'Какая страна выиграла чемпионат мира по футболу 2018?',
            'option_a': 'Франция',
            'option_b': 'Хорватия',
            'option_c': 'Бразилия',
            'option_d': 'Германия',
            'correct_option': 'A',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'sport',
            'question_text': 'Сколько минут длится тайм в футболе?',
            'option_a': '40',
            'option_b': '45',
            'option_c': '50',
            'option_d': '60',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'sport',
            'question_text': 'В каком виде спорта используется шайба?',
            'option_a': 'Футбол',
            'option_b': 'Хоккей',
            'option_c': 'Баскетбол',
            'option_d': 'Волейбол',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'sport',
            'question_text': 'Сколько очков нужно набрать для победы в волейболе?',
            'option_a': '20',
            'option_b': '21',
            'option_c': '25',
            'option_d': '30',
            'correct_option': 'C',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'sport',
            'question_text': 'В каком году проходила Олимпиада в Токио?',
            'option_a': '2018',
            'option_b': '2020',
            'option_c': '2021',
            'option_d': '2022',
            'correct_option': 'C',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'sport',
            'question_text': 'Сколько игроков в команде по хоккею на льду?',
            'option_a': '5',
            'option_b': '6',
            'option_c': '7',
            'option_d': '8',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'sport',
            'question_text': 'Какая страна выиграла больше всего чемпионатов мира по футболу?',
            'option_a': 'Германия',
            'option_b': 'Аргентина',
            'option_c': 'Бразилия',
            'option_d': 'Италия',
            'correct_option': 'C',
            'difficulty': 'hard'
        },
        {
            'theme_code': 'sport',
            'question_text': 'Сколько кругов в олимпийском стадионе?',
            'option_a': '3',
            'option_b': '4',
            'option_c': '5',
            'option_d': '6',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'sport',
            'question_text': 'В каком виде спорта используется мяч овальной формы?',
            'option_a': 'Футбол',
            'option_b': 'Регби',
            'option_c': 'Баскетбол',
            'option_d': 'Волейбол',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'sport',
            'question_text': 'Сколько игроков в команде по бейсболу на поле?',
            'option_a': '8',
            'option_b': '9',
            'option_c': '10',
            'option_d': '11',
            'correct_option': 'B',
            'difficulty': 'hard'
        },
        {
            'theme_code': 'sport',
            'question_text': 'Какая страна выиграла Олимпиаду 2016 в Рио?',
            'option_a': 'США',
            'option_b': 'Китай',
            'option_c': 'Великобритания',
            'option_d': 'Россия',
            'correct_option': 'A',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'sport',
            'question_text': 'Сколько минут длится четверть в баскетболе?',
            'option_a': '10',
            'option_b': '12',
            'option_c': '15',
            'option_d': '20',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'sport',
            'question_text': 'В каком виде спорта используется клюшка?',
            'option_a': 'Футбол',
            'option_b': 'Хоккей',
            'option_c': 'Баскетбол',
            'option_d': 'Волейбол',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'sport',
            'question_text': 'Сколько игроков в команде по водному поло?',
            'option_a': '6',
            'option_b': '7',
            'option_c': '8',
            'option_d': '9',
            'correct_option': 'B',
            'difficulty': 'hard'
        },
        # География (20 вопросов)
        {
            'theme_code': 'geography',
            'question_text': 'Какая самая большая страна по площади?',
            'option_a': 'Канада',
            'option_b': 'Китай',
            'option_c': 'Россия',
            'option_d': 'США',
            'correct_option': 'C',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'geography',
            'question_text': 'Какая самая длинная река в мире?',
            'option_a': 'Амазонка',
            'option_b': 'Нил',
            'option_c': 'Янцзы',
            'option_d': 'Миссисипи',
            'correct_option': 'A',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'geography',
            'question_text': 'Какая столица Австралии?',
            'option_a': 'Сидней',
            'option_b': 'Мельбурн',
            'option_c': 'Канберра',
            'option_d': 'Брисбен',
            'correct_option': 'C',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'geography',
            'question_text': 'Сколько континентов на Земле?',
            'option_a': '5',
            'option_b': '6',
            'option_c': '7',
            'option_d': '8',
            'correct_option': 'C',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'geography',
            'question_text': 'Какая самая высокая гора в мире?',
            'option_a': 'К2',
            'option_b': 'Эверест',
            'option_c': 'Килиманджаро',
            'option_d': 'Мак-Кинли',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'geography',
            'question_text': 'Какая самая большая пустыня в мире?',
            'option_a': 'Гоби',
            'option_b': 'Сахара',
            'option_c': 'Аравийская',
            'option_d': 'Калахари',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'geography',
            'question_text': 'Какая столица Канады?',
            'option_a': 'Торонто',
            'option_b': 'Ванкувер',
            'option_c': 'Оттава',
            'option_d': 'Монреаль',
            'correct_option': 'C',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'geography',
            'question_text': 'Сколько океанов на Земле?',
            'option_a': '3',
            'option_b': '4',
            'option_c': '5',
            'option_d': '6',
            'correct_option': 'C',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'geography',
            'question_text': 'Какая самая маленькая страна в мире?',
            'option_a': 'Монако',
            'option_b': 'Ватикан',
            'option_c': 'Лихтенштейн',
            'option_d': 'Сан-Марино',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'geography',
            'question_text': 'Какая самая длинная река в Европе?',
            'option_a': 'Дунай',
            'option_b': 'Волга',
            'option_c': 'Днепр',
            'option_d': 'Рейн',
            'correct_option': 'B',
            'difficulty': 'hard'
        },
        {
            'theme_code': 'geography',
            'question_text': 'Какая столица Бразилии?',
            'option_a': 'Рио-де-Жанейро',
            'option_b': 'Сан-Паулу',
            'option_c': 'Бразилиа',
            'option_d': 'Салвадор',
            'correct_option': 'C',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'geography',
            'question_text': 'Сколько штатов в США?',
            'option_a': '48',
            'option_b': '50',
            'option_c': '52',
            'option_d': '54',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'geography',
            'question_text': 'Какая самая большая страна Африки по площади?',
            'option_a': 'Египет',
            'option_b': 'Нигерия',
            'option_c': 'Алжир',
            'option_d': 'Судан',
            'correct_option': 'C',
            'difficulty': 'hard'
        },
        {
            'theme_code': 'geography',
            'question_text': 'Какая столица Японии?',
            'option_a': 'Осака',
            'option_b': 'Киото',
            'option_c': 'Токио',
            'option_d': 'Иокогама',
            'correct_option': 'C',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'geography',
            'question_text': 'Сколько стран в Европейском союзе?',
            'option_a': '25',
            'option_b': '27',
            'option_c': '29',
            'option_d': '31',
            'correct_option': 'B',
            'difficulty': 'hard'
        },
        {
            'theme_code': 'geography',
            'question_text': 'Какая самая большая страна Южной Америки?',
            'option_a': 'Аргентина',
            'option_b': 'Бразилия',
            'option_c': 'Перу',
            'option_d': 'Колумбия',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'geography',
            'question_text': 'Какая столица Южной Кореи?',
            'option_a': 'Пусан',
            'option_b': 'Сеул',
            'option_c': 'Инчхон',
            'option_d': 'Тэгу',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'geography',
            'question_text': 'Сколько часовых поясов в России?',
            'option_a': '9',
            'option_b': '10',
            'option_c': '11',
            'option_d': '12',
            'correct_option': 'C',
            'difficulty': 'hard'
        },
        {
            'theme_code': 'geography',
            'question_text': 'Какая самая большая страна Азии по площади?',
            'option_a': 'Китай',
            'option_b': 'Индия',
            'option_c': 'Россия',
            'option_d': 'Казахстан',
            'correct_option': 'C',
            'difficulty': 'hard'
        },
        {
            'theme_code': 'geography',
            'question_text': 'Какая столица Турции?',
            'option_a': 'Стамбул',
            'option_b': 'Анкара',
            'option_c': 'Измир',
            'option_d': 'Бурса',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        # История (20 вопросов)
        {
            'theme_code': 'history',
            'question_text': 'В каком году началась Вторая мировая война?',
            'option_a': '1937',
            'option_b': '1939',
            'option_c': '1941',
            'option_d': '1943',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'history',
            'question_text': 'В каком году пала Берлинская стена?',
            'option_a': '1987',
            'option_b': '1989',
            'option_c': '1991',
            'option_d': '1993',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'history',
            'question_text': 'Кто был первым президентом США?',
            'option_a': 'Томас Джефферсон',
            'option_b': 'Джордж Вашингтон',
            'option_c': 'Джон Адамс',
            'option_d': 'Бенджамин Франклин',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'history',
            'question_text': 'В каком году произошла Октябрьская революция в России?',
            'option_a': '1915',
            'option_b': '1917',
            'option_c': '1919',
            'option_d': '1921',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'history',
            'question_text': 'Кто написал "Войну и мир"?',
            'option_a': 'Федор Достоевский',
            'option_b': 'Лев Толстой',
            'option_c': 'Александр Пушкин',
            'option_d': 'Иван Тургенев',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'history',
            'question_text': 'В каком году распался СССР?',
            'option_a': '1989',
            'option_b': '1990',
            'option_c': '1991',
            'option_d': '1992',
            'correct_option': 'C',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'history',
            'question_text': 'Кто был первым человеком в космосе?',
            'option_a': 'Нил Армстронг',
            'option_b': 'Юрий Гагарин',
            'option_c': 'Валентина Терешкова',
            'option_d': 'Алан Шепард',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'history',
            'question_text': 'В каком году началась Первая мировая война?',
            'option_a': '1912',
            'option_b': '1914',
            'option_c': '1916',
            'option_d': '1918',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'history',
            'question_text': 'Кто был последним императором России?',
            'option_a': 'Александр III',
            'option_b': 'Николай II',
            'option_c': 'Александр II',
            'option_d': 'Павел I',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'history',
            'question_text': 'В каком году человек впервые высадился на Луну?',
            'option_a': '1967',
            'option_b': '1969',
            'option_c': '1971',
            'option_d': '1973',
            'correct_option': 'B',
            'difficulty': 'easy'
        },
        {
            'theme_code': 'history',
            'question_text': 'Кто был первым президентом России?',
            'option_a': 'Михаил Горбачев',
            'option_b': 'Борис Ельцин',
            'option_c': 'Владимир Путин',
            'option_d': 'Дмитрий Медведев',
            'correct_option': 'B',
            'difficulty': 'medium'
        },
        {
            'theme_code': 'history',
            'question_text': 'В каком году произошла Куликовская битва?',
            'option_a': '1360',
            'option_b': '1380',
            'option_c': '1400',
            'option_d': '1420',
            'correct_option': 'B',
            'difficulty': 'hard'
        },
        {
            'theme_code': 'history',
            'question_text': 'Кто написал "Капитал"?',
            'option_a': 'Фридрих Энгельс',
            'option_b': 'Карл Маркс',
            'option_c': 'Владимир Ленин',
            'option_d': 'Иосиф Сталин',
            'correct_option': 'B',
            'difficulty': 'hard'
        },
        {
            'theme_code': 'history',
            'question_text': 'В каком году произошла Великая французская революция?',
            'option_a': '1787',
            'option_b': '1789',
            'option_c': '1791',
            'option_d': '1793',
            'correct_option': 'B',
            'difficulty': 'hard'
        },
        {
            'theme_code': 'history',
            'question_text': 'Кто был первым премьер-министром Великобритании?',
            'option_a': 'Уинстон Черчилль',
            'option_b': 'Роберт Уолпол',
            'option_c': 'Уильям Питт',
            'option_d': 'Бенджамин Дизраэли',
            'correct_option': 'B',
            'difficulty': 'hard'
        },
        {
            'theme_code': 'history',
            'question_text': 'В каком году произошла битва при Ватерлоо?',
            'option_a': '1813',
            'option_b': '1815',
            'option_c': '1817',
            'option_d': '1819',
            'correct_option': 'B',
            'difficulty': 'hard'
        },
        {
            'theme_code': 'history',
            'question_text': 'Кто был первым римским императором?',
            'option_a': 'Юлий Цезарь',
            'option_b': 'Октавиан Август',
            'option_c': 'Нерон',
            'option_d': 'Траян',
            'correct_option': 'B',
            'difficulty': 'hard'
        },
        {
            'theme_code': 'history',
            'question_text': 'В каком году произошла битва на Курской дуге?',
            'option_a': '1941',
            'option_b': '1942',
            'option_c': '1943',
            'option_d': '1944',
            'correct_option': 'C',
            'difficulty': 'hard'
        },
        {
            'theme_code': 'history',
            'question_text': 'Кто был первым королем Англии?',
            'option_a': 'Вильгельм Завоеватель',
            'option_b': 'Альфред Великий',
            'option_c': 'Этельред Неразумный',
            'option_d': 'Эдуард Исповедник',
            'correct_option': 'A',
            'difficulty': 'hard'
        },
        {
            'theme_code': 'history',
            'question_text': 'В каком году произошла битва при Сталинграде?',
            'option_a': '1941',
            'option_b': '1942',
            'option_c': '1943',
            'option_d': '1944',
            'correct_option': 'B',
            'difficulty': 'hard'
        },
    ]
    
    created = 0
    for q_data in questions_data:
        theme = session.query(Theme).filter(Theme.code == q_data['theme_code']).first()
        if not theme:
            logger.warning(f"Theme {q_data['theme_code']} not found, skipping question")
            continue
        
        # Check if question already exists
        existing = session.query(Question).filter(
            Question.question_text == q_data['question_text']
        ).first()
        
        if not existing:
            question = Question(
                theme_id=theme.id,
                question_text=q_data['question_text'],
                option_a=q_data['option_a'],
                option_b=q_data['option_b'],
                option_c=q_data.get('option_c'),
                option_d=q_data.get('option_d'),
                correct_option=q_data['correct_option'],
                difficulty=q_data.get('difficulty', 'medium'),
                source_type='test',
                is_approved=True
            )
            session.add(question)
            created += 1
            logger.info(f"Created question: {q_data['question_text'][:50]}...")
    
    session.commit()
    return created


def create_bots(session):
    """Create test bots."""
    bots_data = [
        {'username': 'Bot_Alpha', 'bot_difficulty': 'novice'},
        {'username': 'Bot_Beta', 'bot_difficulty': 'novice'},
        {'username': 'Bot_Gamma', 'bot_difficulty': 'amateur'},
        {'username': 'Bot_Delta', 'bot_difficulty': 'amateur'},
        {'username': 'Bot_Epsilon', 'bot_difficulty': 'amateur'},
        {'username': 'Bot_Zeta', 'bot_difficulty': 'expert'},
        {'username': 'Bot_Eta', 'bot_difficulty': 'expert'},
        {'username': 'Bot_Theta', 'bot_difficulty': 'expert'},
        {'username': 'Bot_Iota', 'bot_difficulty': 'expert'},
        {'username': 'Bot_Kappa', 'bot_difficulty': 'expert'},
    ]
    
    created = 0
    for bot_data in bots_data:
        existing = session.query(User).filter(
            User.username == bot_data['username'],
            User.is_bot == True
        ).first()
        
        if not existing:
            bot = User(
                telegram_id=None,
                username=bot_data['username'],
                full_name=bot_data['username'],
                is_bot=True,
                bot_difficulty=bot_data['bot_difficulty']
            )
            session.add(bot)
            created += 1
            logger.info(f"Created bot: {bot_data['username']} ({bot_data['bot_difficulty']})")
        else:
            logger.info(f"Bot already exists: {bot_data['username']}")
    
    session.commit()
    return created


def main():
    """Main function."""
    logger.info("Starting test data creation...")
    
    with db_session() as session:
        themes_count = create_themes(session)
        questions_count = create_questions(session)
        bots_count = create_bots(session)
    
    logger.info("=" * 50)
    logger.info("Test data creation completed!")
    logger.info(f"Themes created: {themes_count}")
    logger.info(f"Questions created: {questions_count}")
    logger.info(f"Bots created: {bots_count}")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
