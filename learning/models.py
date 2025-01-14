from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


# Create your models here.


class Word(models.Model):
    """
    Word模型类，继承自Django的models.Model。
    用于在数据库中表示一个单词及其相关信息。

    属性:
    - word: 单词本身，最大长度为100字符。
    - definition: 单词的定义或解释，最大长度为100字符。
    - example: 使用该单词的例句或示例，长度不受限制。
    """
    word = models.CharField(max_length=100)
    definition = models.CharField(max_length=100)
    example = models.TextField()
    phonetic_uk = models.CharField(max_length=100, blank=True)  # 英音发音地址
    phonetic = models.CharField(max_length=100, blank=True)
    phonetic_us = models.CharField(max_length=100, blank=True)  # 美音发音地址
    rating = models.IntegerField(default=0, choices=[(i, str(i)) for i in range(0, 6)])  # 熟练度等级限制在0~5


    def __str__(self):
        """
        返回单词本身的字符串表示。

        返回:
        - self.word: 单词本身。
        """
        return self.word


class UserWordProgress(models.Model):
    """用户学习进度模型

    该模型记录用户对某个单词的学习进度，包括是否已记住、复习次数、最近一次复习时间及下次复习时间
    """
    # 关联用户，当用户被删除时，级联删除该用户的学习进度记录
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    # 关联单词，当单词被删除时，级联删除该单词的学习进度记录
    word = models.ForeignKey(Word, on_delete=models.CASCADE)
    # 记录用户是否已记住该单词，默认为否
    is_memorized = models.BooleanField(default=False)
    # 记录用户对单词的复习次数，默认为0
    review_count = models.IntegerField(default=0)
    # 记录用户最近一次复习该单词的时间，默认为当前时间
    last_review_time = models.DateTimeField(default=timezone.now)
    # 记录用户下次复习该单词的时间，默认为当前时间
    next_review_time = models.DateTimeField(default=timezone.now)

    # 确保同一个用户对同一个单词的学习进度是唯一的
    class Meta:
        unique_together = ['user', 'word']


class Article(models.Model):
    """
    Article模型类，继承自Django的models.Model。
    用于在数据库中表示一篇文章及其相关信息。

    属性:
    - title: 文章的标题，最大长度为100字符。
    - content: 文章的正文内容，长度不受限制。
    - difficulty : 难度等级，取值范围从1到5。

    """
    title = models.CharField(max_length=200)
    content = models.TextField()
    difficulty = models.CharField(max_length=20, choices=[('1', 'easy'), ('2', 'medium'), ('3', 'hard')])

    def __str__(self):
        """
        返回文章的标题字符串表示。
        """
        return self.title
