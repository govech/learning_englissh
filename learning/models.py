from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
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
    rating = models.IntegerField(default=0, choices=[(i, str(i)) for i in range(0, 6)])  # 单词本身的难度评分

    def __str__(self):
        """
        返回单词本身的字符串表示。

        返回:
        - self.word: 单词本身。
        """
        return self.word


# models.py
class UserWord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    word = models.ForeignKey('Word', on_delete=models.CASCADE)
    memory_strength = models.FloatField(default=3.0)  # 记忆强度（1-10）
    next_review = models.DateTimeField(auto_now_add=True)  # 下次复习时间
    error_count = models.IntegerField(default=0)  # 累计错误次数
    last_review = models.DateTimeField(auto_now=True)  # 最后复习时间
    priority = models.FloatField(default=0.0)  # 短期复习优先级
    correct_streak = models.IntegerField(default=0) # 连续正确次数

    class Meta:
        unique_together = ('user', 'word')


class AudioFile(models.Model):
    # 读音对应的单词
    word_text = models.CharField(max_length=100, blank=True, null=True)  # 存储对应的单词名称
    file_path = models.CharField(max_length=100, blank=True, null=True)  # 存储对应的发音文件路径

    LANGUAGE_CHOICES = [
        ('uk', 'UK'),
        ('us', 'US'),
    ]
    # 存储英音还是美音
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, blank=False, null=False)
    def __str__(self):
        return self.word_text


# class UserWordProgress(models.Model):
#     """用户学习进度模型
#
#     该模型记录用户对某个单词的学习进度，包括是否已记住、复习次数、最近一次复习时间及下次复习时间
#     """
#     # 关联用户，当用户被删除时，级联删除该用户的学习进度记录
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     # 关联单词，当单词被删除时，级联删除该单词的学习进度记录
#     word = models.ForeignKey(Word, on_delete=models.CASCADE)
#     # 记录用户是否已记住该单词，默认为否
#     is_memorized = models.BooleanField(default=False)
#     # 记录用户对单词的复习次数，默认为0
#     review_count = models.IntegerField(default=0)
#     # 记录用户最近一次复习该单词的时间，默认为当前时间
#     last_review_time = models.DateTimeField(default=timezone.now)
#     # 记录用户下次复习该单词的时间，默认为当前时间
#     next_review_time = models.DateTimeField(default=timezone.now)
#     # 复习间隔，初始为1天
#     review_interval = models.IntegerField(default=1)
#
#     STATUS_CHOICES = [
#         (0, '新单词'),
#         (1, '熟练度1'),
#         (2, '熟练度2'),
#         (3, '熟练度3'),
#         (4, '熟练度4'),
#         (5, '熟练度5'),
#     ]
#     # 状态：0 (新单词), 1-5(熟练度)
#     status = models.IntegerField(choices=STATUS_CHOICES, default=0)
#
#     def clean(self):
#         if self.status not in dict(self.STATUS_CHOICES):
#             raise ValidationError(f"无效的状态值: {self.status}")
#     def update_review(self, rating):
#         """
#         根据评分更新复习间隔和复习日期。
#         :param rating: 用户评分，表示记忆情况。
#         """
#         if rating == 5:
#             self.review_interval *= 2  # 间隔加倍
#         elif rating == 4:
#             self.review_interval = int(self.review_interval * 1.5)  # 略微延长
#         elif rating == 3:
#             pass  # 保持当前间隔
#         elif rating == 2:
#             self.review_interval = max(1, self.review_interval - 1)  # 缩短复习间隔
#         elif rating == 1:
#             self.review_interval = 1  # 完全忘记，重置间隔为1
#
#         # 更新复习日期
#         self.next_review_date = timezone.now() + timedelta(days=self.review_interval)
#         self.save()
#
#     # 确保同一个用户对同一个单词的学习进度是唯一的
#     class Meta:
#         unique_together = ['user', 'word']


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
