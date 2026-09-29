from django.core.management import call_command
from django.test import TestCase

from questions.models import AnswerOption, Category, ChoiceQuestion, NumericQuestion


class FixtureTests(TestCase):
    def test_fixture_is_available(self):
        call_command('loaddata', 'questions/question_bank.json')

        self.assertEqual(Category.objects.count(), 6)
        self.assertEqual(ChoiceQuestion.objects.count(), 12)
        self.assertEqual(AnswerOption.objects.count(), 48)
        self.assertEqual(NumericQuestion.objects.count(), 12)

        for question in ChoiceQuestion.objects.all():
            self.assertEqual(question.answeroption_set.count(), 4)
            self.assertEqual(question.answeroption_set.filter(is_correct=True).count(), 1)

        for question in NumericQuestion.objects.all():
            self.assertIsInstance(question.correct_answer, int)
