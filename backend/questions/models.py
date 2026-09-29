from django.core.exceptions import ValidationError
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name = 'category'
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name


class BaseQuestion(models.Model):
    category = models.ForeignKey(
        'Category',
        on_delete=models.PROTECT,
        related_name='%(class)ss',
    )
    text = models.TextField()

    class Meta:
        abstract = True


class ChoiceQuestion(BaseQuestion):
    def clean(self):
        super().clean()
        if self.pk is None:
            return

        options = self.answeroption_set.all()
        if options.count() != 4:
            raise ValidationError('A choice question must have exactly four answer options.')

        correct_answers = options.filter(is_correct=True).count()
        if correct_answers != 1:
            raise ValidationError('A choice question must have exactly one correct answer.')

    def __str__(self):
        return self.text


class NumericQuestion(BaseQuestion):
    correct_answer = models.IntegerField()

    def __str__(self):
        return self.text


class AnswerOption(models.Model):
    question = models.ForeignKey(
        ChoiceQuestion,
        on_delete=models.CASCADE,
    )
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text
