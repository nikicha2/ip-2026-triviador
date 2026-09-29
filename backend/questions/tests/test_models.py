from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import TestCase

from questions.models import AnswerOption, Category, ChoiceQuestion, NumericQuestion


class CategoryModelTests(TestCase):
    def test_create_category(self):
        category = Category.objects.create(name='География')
        self.assertEqual(category.name, 'География')

    def test_category_names_must_be_unique(self):
        Category.objects.create(name='История')
        with self.assertRaises(Exception):
            Category.objects.create(name='История')


class ChoiceQuestionModelTests(TestCase):
    def test_create_valid_choice_question(self):
        category = Category.objects.create(name='Наука')
        question = ChoiceQuestion.objects.create(category=category, text='Кой е най-големият океан?')

        options = [
            AnswerOption.objects.create(question=question, text='Атлантически', is_correct=False),
            AnswerOption.objects.create(question=question, text='Индийски', is_correct=False),
            AnswerOption.objects.create(question=question, text='Тихи', is_correct=True),
            AnswerOption.objects.create(question=question, text='Северен ледовит', is_correct=False),
        ]

        self.assertEqual(question.answeroption_set.count(), 4)
        self.assertEqual(question.answeroption_set.filter(is_correct=True).count(), 1)
        self.assertEqual(question.answeroption_set.filter(is_correct=False).count(), 3)
        self.assertEqual(len(options), 4)

    def test_choice_question_validation_rejects_too_few_options(self):
        category = Category.objects.create(name='Спорт')
        question = ChoiceQuestion.objects.create(category=category, text='Питане')
        for label in ['A', 'B', 'C']:
            AnswerOption.objects.create(question=question, text=label, is_correct=False)

        with self.assertRaises(ValidationError):
            question.full_clean()

    def test_choice_question_validation_rejects_too_many_options(self):
        category = Category.objects.create(name='Спорт')
        question = ChoiceQuestion.objects.create(category=category, text='Питане')
        for index in range(5):
            AnswerOption.objects.create(question=question, text=f'Option {index}', is_correct=False)

        with self.assertRaises(ValidationError):
            question.full_clean()

    def test_choice_question_validation_rejects_zero_correct_answers(self):
        category = Category.objects.create(name='Спорт')
        question = ChoiceQuestion.objects.create(category=category, text='Питане')
        for label in ['A', 'B', 'C', 'D']:
            AnswerOption.objects.create(question=question, text=label, is_correct=False)

        with self.assertRaises(ValidationError):
            question.full_clean()

    def test_choice_question_validation_rejects_multiple_correct_answers(self):
        category = Category.objects.create(name='Спорт')
        question = ChoiceQuestion.objects.create(category=category, text='Питане')
        for label, is_correct in [('A', True), ('B', True), ('C', False), ('D', False)]:
            AnswerOption.objects.create(question=question, text=label, is_correct=is_correct)

        with self.assertRaises(ValidationError):
            question.full_clean()


class NumericQuestionModelTests(TestCase):
    def test_create_valid_numeric_question(self):
        category = Category.objects.create(name='История')
        question = NumericQuestion.objects.create(category=category, text='В коя година е основана България?', correct_answer=681)
        self.assertEqual(question.correct_answer, 681)

    def test_numeric_question_requires_correct_answer(self):
        category = Category.objects.create(name='История')
        question = NumericQuestion(category=category, text='В коя година?')
        with self.assertRaises(ValidationError):
            question.full_clean()


class AnswerOptionModelTests(TestCase):
    def test_create_answer_option(self):
        category = Category.objects.create(name='Технологии')
        question = ChoiceQuestion.objects.create(category=category, text='Какво е HTTP?')
        option = AnswerOption.objects.create(question=question, text='Протокол')
        self.assertEqual(option.question, question)
        self.assertFalse(option.is_correct)

    def test_answer_option_cascades_when_question_deleted(self):
        category = Category.objects.create(name='Технологии')
        question = ChoiceQuestion.objects.create(category=category, text='Какво е HTTP?')
        AnswerOption.objects.create(question=question, text='Протокол')
        AnswerOption.objects.create(question=question, text='Мрежа', is_correct=True)

        question.delete()
        self.assertEqual(AnswerOption.objects.filter(question_id__isnull=False).count(), 0)


class CategoryProtectionTests(TestCase):
    def test_category_with_questions_cannot_be_deleted(self):
        category = Category.objects.create(name='География')
        question = ChoiceQuestion.objects.create(category=category, text='Кой океан е най-голям?')
        AnswerOption.objects.create(question=question, text='Тихи', is_correct=True)
        AnswerOption.objects.create(question=question, text='Атлантически', is_correct=False)
        AnswerOption.objects.create(question=question, text='Индийски', is_correct=False)
        AnswerOption.objects.create(question=question, text='Северен ледовит', is_correct=False)

        with self.assertRaises(ProtectedError):
            category.delete()


class FixtureLoadingTests(TestCase):
    fixtures = ['questions/question_bank.json']

    def test_question_bank_fixture_loads(self):
        self.assertEqual(Category.objects.count(), 6)
        self.assertEqual(ChoiceQuestion.objects.count(), 12)
        self.assertEqual(AnswerOption.objects.count(), 48)
        self.assertEqual(NumericQuestion.objects.count(), 12)

        for question in ChoiceQuestion.objects.all():
            self.assertEqual(question.answeroption_set.count(), 4)
            self.assertEqual(question.answeroption_set.filter(is_correct=True).count(), 1)

        for question in NumericQuestion.objects.all():
            self.assertIsInstance(question.correct_answer, int)
