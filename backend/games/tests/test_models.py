from django.test import TestCase

from auth_app.models import User
from games.models import Game, GamePlayer, Round, RoundAnswer
from questions.models import AnswerOption, Category, ChoiceQuestion, NumericQuestion


class GameModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', email='alice@example.com', password='pass1234')

    def test_create_game_uses_waiting_default(self):
        game = Game.objects.create(created_by=self.user)
        self.assertEqual(game.status, Game.WAITING)

    def test_game_timestamps_are_populated_automatically(self):
        game = Game.objects.create(created_by=self.user)
        self.assertIsNotNone(game.created_at)
        self.assertIsNone(game.started_at)
        self.assertIsNone(game.finished_at)

    def test_game_allows_optional_timestamps(self):
        game = Game.objects.create(created_by=self.user, started_at=None, finished_at=None)
        self.assertIsNone(game.started_at)
        self.assertIsNone(game.finished_at)

    def test_create_game_player_with_defaults(self):
        game = Game.objects.create(created_by=self.user)
        player = GamePlayer.objects.create(game=game, user=self.user, player_order=1)
        self.assertEqual(player.score, 0)
        self.assertTrue(player.is_active)
        self.assertIsNotNone(player.joined_at)

    def test_create_rounds_with_choice_and_numeric_questions(self):
        category = Category.objects.create(name='Geography')
        choice_question = ChoiceQuestion.objects.create(category=category, text='Capital of Bulgaria?')
        for label, is_correct in [('Sofia', True), ('Plovdiv', False), ('Varna', False), ('Ruse', False)]:
            AnswerOption.objects.create(question=choice_question, text=label, is_correct=is_correct)
        numeric_question = NumericQuestion.objects.create(category=category, text='How many continents?', correct_answer=7)

        game = Game.objects.create(created_by=self.user)
        choice_round = Round.objects.create(
            game=game,
            number=1,
            status=Round.PENDING,
            question_type=Round.CHOICE,
            choice_question=choice_question,
        )
        numeric_round = Round.objects.create(
            game=game,
            number=2,
            status=Round.PENDING,
            question_type=Round.NUMERIC,
            numeric_question=numeric_question,
        )

        self.assertEqual(choice_round.choice_question, choice_question)
        self.assertIsNone(choice_round.numeric_question)
        self.assertEqual(numeric_round.numeric_question, numeric_question)
        self.assertIsNone(numeric_round.choice_question)

    def test_create_round_answer_valid_data(self):
        category = Category.objects.create(name='Math')
        game = Game.objects.create(created_by=self.user)
        player = GamePlayer.objects.create(game=game, user=self.user, player_order=1)
        choice_question = ChoiceQuestion.objects.create(category=category, text='2 + 2?')
        for label, is_correct in [('3', False), ('4', True), ('5', False), ('6', False)]:
            AnswerOption.objects.create(question=choice_question, text=label, is_correct=is_correct)
        selected_option = choice_question.answeroption_set.get(is_correct=True)
        round_obj = Round.objects.create(
            game=game,
            number=1,
            status=Round.OPEN,
            question_type=Round.CHOICE,
            choice_question=choice_question,
        )

        answer = RoundAnswer.objects.create(
            round=round_obj,
            player=player,
            selected_option=selected_option,
            is_correct=True,
            points_awarded=10,
            submitted_at=None,
        )

        self.assertEqual(answer.selected_option, selected_option)
        self.assertIsNone(answer.numeric_value)
        self.assertTrue(answer.is_correct)
        self.assertEqual(answer.points_awarded, 10)

    def test_related_managers_and_str_methods(self):
        game = Game.objects.create(created_by=self.user)
        GamePlayer.objects.create(game=game, user=self.user, player_order=1)
        self.assertEqual(game.game_players.count(), 1)
        self.assertEqual(self.user.created_games.count(), 1)
        self.assertEqual(str(game), f'Game {game.pk} - {game.status}')

        category = Category.objects.create(name='History')
        choice_question = ChoiceQuestion.objects.create(category=category, text='What is 5 + 5?')
        for label, is_correct in [('8', False), ('10', True), ('12', False), ('14', False)]:
            AnswerOption.objects.create(question=choice_question, text=label, is_correct=is_correct)
        round_obj = Round.objects.create(
            game=game,
            number=1,
            status=Round.PENDING,
            question_type=Round.CHOICE,
            choice_question=choice_question,
        )
        self.assertEqual(game.rounds.count(), 1)
        self.assertEqual(round_obj.game, game)
        self.assertEqual(str(round_obj), f'Round {round_obj.number} ({round_obj.get_question_type_display()})')
