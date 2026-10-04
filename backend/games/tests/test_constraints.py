from django.db import IntegrityError, transaction
from django.test import TestCase

from auth_app.models import User
from games.models import Game, GamePlayer, Round, RoundAnswer
from questions.models import AnswerOption, Category, ChoiceQuestion, NumericQuestion


class GameConstraintTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', email='alice@example.com', password='pass1234')
        self.other_user = User.objects.create_user(username='bob', email='bob@example.com', password='pass1234')
        self.game = Game.objects.create(created_by=self.user)

    def test_duplicate_participation_in_same_game_is_rejected(self):
        GamePlayer.objects.create(game=self.game, user=self.user, player_order=1)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                GamePlayer.objects.create(game=self.game, user=self.user, player_order=2)

    def test_duplicate_player_order_within_game_is_rejected(self):
        GamePlayer.objects.create(game=self.game, user=self.user, player_order=1)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                GamePlayer.objects.create(game=self.game, user=self.other_user, player_order=1)

    def test_duplicate_round_number_within_game_is_rejected(self):
        category = Category.objects.create(name='Sports')
        question = ChoiceQuestion.objects.create(category=category, text='Who won Euro 2024?')
        for label, is_correct in [('Italy', False), ('France', True), ('Germany', False), ('Spain', False)]:
            AnswerOption.objects.create(question=question, text=label, is_correct=is_correct)

        Round.objects.create(game=self.game, number=1, question_type=Round.CHOICE, choice_question=question)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Round.objects.create(game=self.game, number=1, question_type=Round.CHOICE, choice_question=question)

    def test_round_must_reference_exactly_one_question(self):
        category = Category.objects.create(name='Science')
        question = ChoiceQuestion.objects.create(category=category, text='Which planet is red?')
        for label, is_correct in [('Earth', False), ('Mars', True), ('Venus', False), ('Jupiter', False)]:
            AnswerOption.objects.create(question=question, text=label, is_correct=is_correct)

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Round.objects.create(game=self.game, number=1, question_type=Round.CHOICE)

        numeric_question = NumericQuestion.objects.create(category=category, text='What is 2 + 2?', correct_answer=4)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Round.objects.create(
                    game=self.game,
                    number=2,
                    question_type=Round.CHOICE,
                    choice_question=question,
                    numeric_question=numeric_question,
                )

    def test_round_type_must_match_question_reference(self):
        category = Category.objects.create(name='Science')
        question = ChoiceQuestion.objects.create(category=category, text='Which planet is red?')
        for label, is_correct in [('Earth', False), ('Mars', True), ('Venus', False), ('Jupiter', False)]:
            AnswerOption.objects.create(question=question, text=label, is_correct=is_correct)

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Round.objects.create(game=self.game, number=1, question_type=Round.NUMERIC, choice_question=question)

    def test_duplicate_answer_for_same_player_and_round_is_rejected(self):
        category = Category.objects.create(name='Math')
        question = ChoiceQuestion.objects.create(category=category, text='2 + 2?')
        for label, is_correct in [('3', False), ('4', True), ('5', False), ('6', False)]:
            AnswerOption.objects.create(question=question, text=label, is_correct=is_correct)
        round_obj = Round.objects.create(game=self.game, number=1, question_type=Round.CHOICE, choice_question=question)
        player = GamePlayer.objects.create(game=self.game, user=self.user, player_order=1)
        option = question.answeroption_set.get(is_correct=True)

        RoundAnswer.objects.create(round=round_obj, player=player, selected_option=option, is_correct=True)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                RoundAnswer.objects.create(round=round_obj, player=player, selected_option=option, is_correct=True)

    def test_answer_must_not_contain_both_selected_option_and_numeric_value(self):
        category = Category.objects.create(name='Math')
        question = ChoiceQuestion.objects.create(category=category, text='2 + 2?')
        for label, is_correct in [('3', False), ('4', True), ('5', False), ('6', False)]:
            AnswerOption.objects.create(question=question, text=label, is_correct=is_correct)
        round_obj = Round.objects.create(game=self.game, number=1, question_type=Round.CHOICE, choice_question=question)
        player = GamePlayer.objects.create(game=self.game, user=self.user, player_order=1)
        option = question.answeroption_set.get(is_correct=True)

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                RoundAnswer.objects.create(
                    round=round_obj,
                    player=player,
                    selected_option=option,
                    numeric_value=4,
                    is_correct=True,
                )

    def test_draft_answer_is_allowed_when_not_submitted(self):
        category = Category.objects.create(name='Math')
        question = ChoiceQuestion.objects.create(category=category, text='2 + 2?')
        for label, is_correct in [('3', False), ('4', True), ('5', False), ('6', False)]:
            AnswerOption.objects.create(question=question, text=label, is_correct=is_correct)
        round_obj = Round.objects.create(game=self.game, number=1, question_type=Round.CHOICE, choice_question=question)
        player = GamePlayer.objects.create(game=self.game, user=self.user, player_order=1)

        answer = RoundAnswer.objects.create(round=round_obj, player=player, submitted_at=None)
        self.assertIsNone(answer.selected_option)
        self.assertIsNone(answer.numeric_value)
